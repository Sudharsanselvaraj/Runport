"""Evaluation benchmark coordinator and run execution engine."""

import uuid
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from runport.core.budget import BudgetExceededError, BudgetService
from runport.dataset.manager import DatasetManager
from runport.evaluation.evaluator import RubricEvaluator
from runport.evaluation.replay_scoring import mean_or_none
from runport.core.live_guard import LiveAuthorization, require_live_authorization
from runport.providers.base import (
    BaseProvider,
    LiveNotAuthorizedError,
    ProviderRequest,
    UsageUnavailableError,
    require_complete_usage,
)
from runport.providers.openrouter import OpenRouterAdapter
from runport.schemas.evaluation import DatasetSplit, EvaluationCase
from runport.storage.db import DatabaseManager


class BenchmarkRunReport(BaseModel):
    """Aggregated report of an evaluation benchmark run."""

    run_id: str
    timestamp: str
    model_id: str
    dataset_path: str
    total_cases: int
    completed_cases: int
    failed_cases: int
    total_cost_usd: Decimal
    # None = nothing measured (for example, no labelled cases). Never reported as 0.
    mean_latency_ms: Optional[float]
    mean_accuracy: Optional[float]
    mean_groundedness: Optional[float]
    mean_overall_score: Optional[float]
    results: List[Dict[str, Any]] = Field(default_factory=list)
    notes: Optional[str] = None


class BenchmarkRunner:
    """Orchestrates model benchmarking with budget checks, confidentiality gating, and run persistence."""

    def __init__(
        self,
        db_mgr: Optional[DatabaseManager] = None,
        budget_service: Optional[BudgetService] = None,
        provider: Optional[BaseProvider] = None,
    ):
        self.db_mgr = db_mgr or DatabaseManager()
        self.budget_service = budget_service or BudgetService(db=self.db_mgr)
        self.provider = provider or OpenRouterAdapter()
        self.evaluator = RubricEvaluator()

    def run(
        self,
        model_id: str,
        dataset_path: Path,
        split: Optional[DatasetSplit] = None,
        live_authorization: Optional[LiveAuthorization] = None,
    ) -> BenchmarkRunReport:
        """Runs real requests for the specified dataset. Needs a live authorization covering the model; there is no simulated mode."""
        require_live_authorization(live_authorization, model_id)
        run_id = f"run_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"
        now_iso = datetime.now(timezone.utc).isoformat()

        # 1. Load dataset
        manager = DatasetManager()
        all_cases = manager.load_jsonl(dataset_path)

        if split and split != DatasetSplit.UNASSIGNED:
            cases = [c for c in all_cases if c.split == split]
        else:
            cases = all_cases

        if not cases:
            raise ValueError(f"No cases found for evaluation in {dataset_path} (split: {split})")

        # 2. Budget Preflight Estimate
        estimated_cost = Decimal("0.0003") * Decimal(len(cases))
        # Checks local policy limit
        self.budget_service.check_preflight_budget(
            estimated_cost_usd=estimated_cost,
            is_pilot=True,
            model_id=model_id,
        )

        completed_results: List[Dict[str, Any]] = []
        failed_count = 0
        total_run_cost = Decimal("0.0000")

        # 3. Execution Loop
        for idx, case in enumerate(cases, 1):
            # Enforce Fail-Closed Confidentiality Gate
            OpenRouterAdapter.validate_case_confidentiality(case)

            prompt_messages = [
                {
                    "role": "system",
                    "content": (
                        "You are an AI benchmark evaluator. Answer accurately, ground all answers in academic guidelines, and never invent fees or policies."
                    ),
                },
                {"role": "user", "content": case.query},
            ]

            request = ProviderRequest(
                model_id=model_id,
                messages=prompt_messages,
                live_authorized=True,
                case_id=case.id,
            )

            try:
                response = self.provider.generate(request)
                try:
                    require_complete_usage(response)
                except UsageUnavailableError:
                    self.budget_service.record_unresolved_spend(
                        f"tx_{run_id}_{case.id}", model_id, "openrouter", f"Evaluation case {case.id}: response lacked usable cost or token counts", run_id
                    )
                    raise
                exec_id = f"exec_{run_id}_{case.id}"
                score_id = f"score_{run_id}_{case.id}"

                score = self.evaluator.evaluate(
                    score_id=score_id,
                    execution_id=exec_id,
                    generated_output=response.output_text,
                    expected_answer=case.expected_answer,
                )

                self.budget_service.record_spend(
                    transaction_id=f"tx_{run_id}_{case.id}",
                    model_id=model_id,
                    provider="openrouter",
                    amount_usd=response.cost_usd,
                    description=f"Evaluation case {case.id}",
                    run_id=run_id,
                    is_pilot=True,
                    is_preflight_estimate=False,
                    cost_basis=response.cost_basis,
                )
                total_run_cost += response.cost_usd

                result_entry = {
                    "result_id": f"res_{run_id}_{case.id}",
                    "run_id": run_id,
                    "case_id": case.id,
                    "prompt": case.query,
                    "expected_answer": case.expected_answer or "",
                    "generated_output": response.output_text,
                    "latency_ms": response.latency_ms,
                    "prompt_tokens": response.prompt_tokens,
                    "completion_tokens": response.completion_tokens,
                    "cost_usd": str(response.cost_usd),
                    "accuracy": score.accuracy,
                    "groundedness": score.groundedness,
                    "format_adherence": score.format_adherence,
                    "overall_score": score.overall_score,
                    "evaluator_notes": score.notes or "",
                }
                completed_results.append(result_entry)

            except Exception as e:
                failed_count += 1
                if isinstance(e, (BudgetExceededError, UsageUnavailableError, LiveNotAuthorizedError)):
                    raise

        # 4. Aggregate metrics
        # Means cover measured values only; unlabelled cases have no accuracy and are left out.
        n_comp = len(completed_results)
        mean_lat = mean_or_none((r["latency_ms"] for r in completed_results), ndigits=2)
        mean_acc = mean_or_none(r["accuracy"] for r in completed_results)
        mean_grd = mean_or_none(r["groundedness"] for r in completed_results)
        mean_ovr = mean_or_none(r["overall_score"] for r in completed_results)

        run_summary = {
            "run_id": run_id,
            "timestamp": now_iso,
            "model_id": model_id,
            "dataset_path": str(dataset_path),
            "total_cases": len(cases),
            "completed_cases": n_comp,
            "failed_cases": failed_count,
            "total_cost_usd": str(total_run_cost),
            "mean_latency_ms": mean_lat,
            "mean_accuracy": mean_acc,
            "mean_groundedness": mean_grd,
            "mean_overall_score": mean_ovr,
            "is_dry_run": False,  # legacy column: this tool no longer produces simulated runs
            "notes": f"Evaluation over {dataset_path.name} (split: {split or 'ALL'})",
        }

        # 5. Persist to SQLite
        self.db_mgr.save_evaluation_run(run_summary)
        if completed_results:
            self.db_mgr.save_evaluation_results(completed_results)

        return BenchmarkRunReport(
            run_id=run_id,
            timestamp=now_iso,
            model_id=model_id,
            dataset_path=str(dataset_path),
            total_cases=len(cases),
            completed_cases=n_comp,
            failed_cases=failed_count,
            total_cost_usd=total_run_cost,
            mean_latency_ms=mean_lat,
            mean_accuracy=mean_acc,
            mean_groundedness=mean_grd,
            mean_overall_score=mean_ovr,
            results=completed_results,
            notes=run_summary["notes"],
        )

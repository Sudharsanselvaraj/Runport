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
        """Runs real requests for the dataset through GenericRunner (the one guarded executor).

        Needs a live authorization covering the model. Dataset cases are validated (EvaluationCase), the
        confidentiality gate, budget preflight, persistence and spend booking are GenericRunner's. A response
        without usable cost is booked UNRESOLVED, the run halts, and UsageUnavailableError is raised.
        """
        from runport.connectors.openrouter import OpenRouterTarget
        from runport.core.approvers import TokenApprover
        from runport.core.workspace import load_workspace_config
        from runport.runs.executor import GenericRunner
        from runport.runs.planner import ExecutionPlan
        from runport.services.execution import rubric_case_scorer

        require_live_authorization(live_authorization, model_id)
        all_cases = DatasetManager().load_jsonl(dataset_path)
        cases = [c for c in all_cases if c.split == split] if split and split != DatasetSplit.UNASSIGNED else all_cases
        if not cases:
            raise ValueError(f"No cases found for evaluation in {dataset_path} (split: {split})")
        for case in cases:
            OpenRouterAdapter.validate_case_confidentiality(case)  # fail before anything is planned or sent

        target = OpenRouterTarget(model_id=model_id, adapter=self.provider)  # type: ignore[arg-type]

        case_dicts = [c.model_dump(mode="json") for c in cases]
        plan = ExecutionPlan(
            plan_id=f"benchmark-{uuid.uuid4().hex[:8]}",
            target_ids=[model_id],
            dataset_path=str(dataset_path),
            dataset_hash=DatasetManager.compute_sha256(dataset_path),
            total_cases=len(case_dicts),
            budget_cap_usd=self.budget_service.policy.per_run_ceiling_usd,
            is_live=True,
        )
        workspace = load_workspace_config()
        runner = GenericRunner(budget_service=self.budget_service, db=self.db_mgr, workspace=workspace)
        approver = TokenApprover(token=plan.fingerprint, enabled=True, operator="live_authorization")
        run = runner.execute_plan(plan, {model_id: target}, case_dicts, approver=approver, case_scorer=rubric_case_scorer)[0]
        if run.halted_reason:
            if run.halt_kind == "budget":
                raise BudgetExceededError(run.halted_reason)
            raise UsageUnavailableError(run.halted_reason)

        rows = self.db_mgr.get_evaluation_results_for_run(run.run_id)
        completed = [r for r in rows if r.get("generated_output")]
        saved = self.db_mgr.get_evaluation_run(run.run_id) or {}
        return BenchmarkRunReport(
            run_id=run.run_id,
            timestamp=str(saved.get("timestamp") or datetime.now(timezone.utc).isoformat()),
            model_id=model_id,
            dataset_path=str(dataset_path),
            total_cases=len(case_dicts),
            completed_cases=run.successful_cases,
            failed_cases=run.failed_cases + run.invalid_cases + run.skipped_cases,
            total_cost_usd=run.total_spend_usd,
            mean_latency_ms=mean_or_none((r["latency_ms"] for r in completed), ndigits=2),
            mean_accuracy=mean_or_none(r["accuracy"] for r in completed),
            mean_groundedness=mean_or_none(r["groundedness"] for r in completed),
            mean_overall_score=mean_or_none(r["overall_score"] for r in completed),
            results=completed,
            notes=f"Evaluation over {Path(dataset_path).name} (split: {split or 'ALL'}) via GenericRunner",
        )

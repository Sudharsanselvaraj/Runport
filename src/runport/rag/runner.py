"""Runner orchestrating decoupled end-to-end RAG benchmarking across candidate models and retrievers."""

import uuid
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence

from runport.core.budget import BudgetExceededError, BudgetService
from runport.dataset.manager import DatasetManager
from runport.core.live_guard import LiveAuthorization, require_live_authorization
from runport.core.approvers import TokenApprover
from runport.core.workspace import load_workspace_config
from runport.providers.base import BaseProvider, UsageUnavailableError
from runport.rag.target import RagPipelineTarget, rag_case_scorer
from runport.runs.executor import GenericRunner
from runport.runs.planner import ExecutionPlan
from runport.targets.base import TargetStatus
from runport.providers.openrouter import OpenRouterAdapter
from runport.rag.evaluator import RAGSystemEvaluator
from runport.rag.models import RAGBenchmarkReport, RAGCaseEvaluation
from runport.rag.retriever import BaseRetriever
from runport.schemas.evaluation import DatasetSplit, EvaluationCase
from runport.storage.db import DatabaseManager


class RAGBenchmarkRunner:
    """Orchestrates decoupled RAG evaluation measuring retrieval and generation separately."""

    def __init__(
        self,
        retriever: BaseRetriever,
        db_mgr: Optional[DatabaseManager] = None,
        budget_service: Optional[BudgetService] = None,
        provider: Optional[BaseProvider] = None,
        top_k: int = 2,
    ):
        self.db_mgr = db_mgr or DatabaseManager()
        self.budget_service = budget_service or BudgetService(db=self.db_mgr)
        self.provider = provider or OpenRouterAdapter()
        self.retriever = retriever
        self.evaluator = RAGSystemEvaluator()
        self.top_k = top_k

    def _load_cases(self, dataset_path: Path, split: Optional[DatasetSplit]) -> List[EvaluationCase]:
        all_cases = DatasetManager().load_jsonl(dataset_path)
        cases = [c for c in all_cases if c.split == split] if split and split != DatasetSplit.UNASSIGNED else all_cases
        if not cases:
            raise ValueError(f"No cases found for evaluation in {dataset_path} (split: {split})")
        for c in cases:
            OpenRouterAdapter.validate_case_confidentiality(c)  # fail before anything is planned or sent
        return cases

    def target_for(self, model_id: str) -> RagPipelineTarget:
        return RagPipelineTarget(model_id=model_id, retriever=self.retriever, adapter=self.provider, top_k=self.top_k)

    def spec_for(self, model_id: str) -> Dict[str, Any]:
        """What a plan fingerprint binds for this pipeline (no secrets)."""
        return {"type": "rag", "model": model_id, "retriever": self.retriever.__class__.__name__, "top_k": self.top_k}

    def run(
        self,
        model_id: str,
        dataset_path: Path,
        split: Optional[DatasetSplit] = None,
        live_authorization: Optional[LiveAuthorization] = None,
    ) -> RAGBenchmarkReport:
        """Runs the RAG benchmark with real requests through GenericRunner. Needs a live authorization covering the model."""
        require_live_authorization(live_authorization, model_id)
        cases = self._load_cases(dataset_path, split)
        case_dicts = [c.model_dump(mode="json") for c in cases]
        plan = ExecutionPlan(
            plan_id=f"rag-{uuid.uuid4().hex[:8]}",
            target_ids=[model_id],
            dataset_path=str(dataset_path),
            dataset_hash=DatasetManager.compute_sha256(dataset_path),
            total_cases=len(case_dicts),
            budget_cap_usd=self.budget_service.policy.per_run_ceiling_usd,
            prompt_template_hash=f"rag:{self.retriever.__class__.__name__}:top_k={self.top_k}",
            is_live=True,
        )
        runner = GenericRunner(budget_service=self.budget_service, db=self.db_mgr, workspace=load_workspace_config())
        approver = TokenApprover(token=plan.fingerprint, enabled=True, operator="live_authorization")
        run = runner.execute_plan(plan, {model_id: self.target_for(model_id)}, case_dicts, approver=approver, case_scorer=rag_case_scorer)[0]
        return self.report_from_run(model_id, run, cases, dataset_path, split)

    def run_planned(
        self,
        service: Any,
        model_ids: Sequence[str],
        dataset_path: Path,
        split: Optional[DatasetSplit],
        approve: Callable[[Any], None],
    ) -> List[RAGBenchmarkReport]:
        """Plan -> approve -> execute through ExecutionService (one plan and one approval for all models).

        ``approve`` receives the PlanSummary and must approve it through a human channel (e.g. the CLI phrase).
        """
        cases = self._load_cases(dataset_path, split)
        case_dicts = [c.model_dump(mode="json") for c in cases]
        targets = {m: self.target_for(m) for m in model_ids}
        specs = {m: self.spec_for(m) for m in model_ids}
        plan = service.plan(targets, specs, case_dicts, dataset_label=Path(dataset_path).name, requested_by="cli")
        if plan.blockers:
            raise BudgetExceededError("Plan is blocked: " + "; ".join(plan.blockers))
        approve(plan)
        outcome = service.execute(plan.plan_id, targets, specs, case_dicts, case_scorer=rag_case_scorer)
        by_target = {r.target_id: r for r in outcome.runs}
        return [self.report_from_run(m, by_target[m], cases, dataset_path, split) for m in model_ids if m in by_target]

    def report_from_run(
        self,
        model_id: str,
        run: Any,
        cases: List[EvaluationCase],
        dataset_path: Path,
        split: Optional[DatasetSplit],
    ) -> RAGBenchmarkReport:
        """RAG metrics (retrieval vs generation, abstention, failure attribution) from a GenericRunner run."""
        if run.halted_reason:
            if run.halt_kind == "budget":
                raise BudgetExceededError(run.halted_reason)
            raise UsageUnavailableError(run.halted_reason)
        run_id = run.run_id
        now_iso = (self.db_mgr.get_evaluation_run(run_id) or {}).get("timestamp") or datetime.now(timezone.utc).isoformat()

        case_results: List[RAGCaseEvaluation] = []
        total_cost = run.total_spend_usd
        failure_breakdown: Dict[str, int] = {
            "SYSTEM_SUCCESS": 0,
            "RETRIEVAL_FAILURE": 0,
            "GENERATION_FAILURE": 0,
            "PARAMETRIC_MEMORY_RESCUE": 0,
        }

        # Per-case RAG metrics from what GenericRunner executed (failed generations carry no answer to score).
        for case, res in zip(cases, run.case_results):
            if res.status != TargetStatus.SUCCESS:
                continue
            retrieval = res.metadata.get("retrieval") or {}
            chunks: List[str] = list(retrieval.get("chunks") or [])
            generated = res.output_text or ""
            gen_latency = float(res.metadata.get("generation_latency_ms") or 0.0)
            ret_latency = float(retrieval.get("latency_ms") or 0.0)
            ans_corr, groundedness = self.evaluator.evaluate_generation(
                generated_output=generated, retrieved_chunks=chunks, expected_answer=case.expected_answer
            )

            # Ground-Truth Source Retrieval Metrics against case.relevant_record_ids
            rel_set = set(case.relevant_record_ids)
            ret_ids = list(retrieval.get("record_ids") or [])

            recall_k = 0.0
            precision_k = 0.0
            rr = 0.0
            ret_hit = False

            if rel_set:
                hits = [r for r in ret_ids if r in rel_set]
                recall_k = round(len(hits) / len(rel_set), 4)
                precision_k = round(len(hits) / len(ret_ids), 4) if ret_ids else 0.0
                ret_hit = len(hits) > 0

                for rank_idx, r in enumerate(ret_ids, 1):
                    if r in rel_set:
                        rr = round(1.0 / rank_idx, 4)
                        break

            # Abstention evaluation
            abstention_corr = None
            if case.abstention_expected:
                lower_gen = generated.lower()
                abstention_phrases = [
                    "does not contain",
                    "not mentioned",
                    "not specified",
                    "consult",
                    "counselor",
                    "contact",
                    "insufficient",
                    "unable to",
                    "not found",
                    "official portal",
                    "reach out",
                    "no information",
                    "lacks details",
                ]
                abstention_corr = 1.0 if any(p in lower_gen for p in abstention_phrases) else 0.0

            # Updated Failure Attribution
            if case.abstention_expected:
                attribution = "ABSTENTION_SUCCESS" if abstention_corr == 1.0 else "OVERCONFIDENT_HALLUCINATION"
            elif rel_set:
                if ret_hit and (ans_corr is not None and ans_corr >= 0.70) and groundedness >= 0.40:
                    attribution = "SYSTEM_SUCCESS"
                elif not ret_hit:
                    attribution = "RETRIEVAL_FAILURE"
                else:
                    attribution = "GENERATION_FAILURE"
            else:
                attribution = self.evaluator.attribute_failure(
                    retrieval_hit_rate=float(retrieval.get("hit_rate") or 0.0),
                    answer_correctness=ans_corr,
                    groundedness=groundedness,
                )
            failure_breakdown[attribution] = failure_breakdown.get(attribution, 0) + 1

            e2e_lat = round(ret_latency + gen_latency, 2)

            case_eval = RAGCaseEvaluation(
                case_id=case.id,
                model_id=model_id,
                retriever_id=str(retrieval.get("retriever_id") or self.retriever.__class__.__name__),
                query=case.query,
                retrieved_chunks=chunks,
                retrieved_record_ids=ret_ids,
                generated_answer=generated,
                expected_answer=case.expected_answer,
                source_status=str(getattr(case.source_status, "value", case.source_status)),
                relevant_record_ids=case.relevant_record_ids,
                abstention_expected=case.abstention_expected,
                recall_at_k=recall_k,
                precision_at_k=precision_k,
                reciprocal_rank=rr,
                retrieval_hit=ret_hit,
                retrieval_hit_rate=float(retrieval.get("hit_rate") or 0.0),
                retrieval_precision=float(retrieval.get("precision") or 0.0),
                retrieval_latency_ms=ret_latency,
                answer_correctness=ans_corr,
                groundedness=groundedness,
                abstention_correctness=abstention_corr,
                generation_latency_ms=gen_latency,
                e2e_latency_ms=e2e_lat,
                cost_usd=res.cost_usd if res.cost_usd is not None else Decimal("0"),
                failure_attribution=attribution,
            )
            case_results.append(case_eval)

        # 4. Compute Aggregated Metrics
        n = len(case_results)
        verified_cases = [c for c in case_results if c.relevant_record_ids]
        n_ver = len(verified_cases)

        unresolved_cases = [c for c in case_results if c.abstention_expected]
        n_unres = len(unresolved_cases)

        mean_recall = round(sum(c.recall_at_k for c in verified_cases) / n_ver, 4) if n_ver else 0.0
        mean_precision = round(sum(c.precision_at_k for c in verified_cases) / n_ver, 4) if n_ver else 0.0
        mean_mrr = round(sum(c.reciprocal_rank for c in verified_cases) / n_ver, 4) if n_ver else 0.0
        ver_hit_rate = round(sum(1.0 if c.retrieval_hit else 0.0 for c in verified_cases) / n_ver, 4) if n_ver else 0.0

        abstention_acc = round(sum(c.abstention_correctness or 0.0 for c in unresolved_cases) / n_unres, 4) if n_unres else 0.0

        diag_kw_hit = round(sum(c.retrieval_hit_rate for c in case_results) / n, 4) if n else 0.0
        diag_kw_prec = round(sum(c.retrieval_precision for c in case_results) / n, 4) if n else 0.0
        mean_ret_lat = round(sum(c.retrieval_latency_ms for c in case_results) / n, 2) if n else 0.0

        measured_corr = [c.answer_correctness for c in case_results if c.answer_correctness is not None]
        mean_ans_corr: Optional[float] = round(sum(measured_corr) / len(measured_corr), 4) if measured_corr else None
        mean_grd = round(sum(c.groundedness for c in case_results) / n, 4) if n else 0.0
        mean_gen_lat = round(sum(c.generation_latency_ms for c in case_results) / n, 2) if n else 0.0
        mean_e2e_lat = round(sum(c.e2e_latency_ms for c in case_results) / n, 2) if n else 0.0

        # 5. GenericRunner persisted the run, its per-case results and the spend; add the RAG summary to the run header.
        saved = self.db_mgr.get_evaluation_run(run_id) or {}
        self.db_mgr.save_evaluation_run(
            {
                **saved,
                "run_id": run_id,
                "timestamp": now_iso,
                "model_id": model_id,
                "dataset_path": str(dataset_path),
                "total_cases": len(cases),
                "completed_cases": run.successful_cases,
                "failed_cases": run.failed_cases + run.invalid_cases + run.skipped_cases,
                "total_cost_usd": str(total_cost),
                "mean_latency_ms": mean_e2e_lat if n else None,
                "is_dry_run": False,
                "notes": (
                    f"RAG benchmark via GenericRunner (retriever={self.retriever.__class__.__name__}, split={split or 'ALL'}, "
                    f"top_k={self.top_k}, recall@k={mean_recall}, mrr={mean_mrr})"
                ),
            }
        )

        return RAGBenchmarkReport(
            run_id=run_id,
            timestamp=now_iso,
            model_id=model_id,
            retriever_id=self.retriever.__class__.__name__,
            split=str(split or "ALL"),
            total_cases=n,
            verified_cases_count=n_ver,
            unresolved_cases_count=n_unres,
            mean_recall_at_k=mean_recall,
            mean_precision_at_k=mean_precision,
            mean_reciprocal_rank=mean_mrr,
            verified_retrieval_hit_rate=ver_hit_rate,
            mean_retrieval_latency_ms=mean_ret_lat,
            abstention_accuracy=abstention_acc,
            diagnostic_keyword_hit_rate=diag_kw_hit,
            mean_retrieval_hit_rate=diag_kw_hit,
            mean_retrieval_precision=diag_kw_prec,
            mean_answer_correctness=mean_ans_corr,
            mean_groundedness=mean_grd,
            mean_generation_latency_ms=mean_gen_lat,
            mean_e2e_latency_ms=mean_e2e_lat,
            total_cost_usd=total_cost,
            failure_breakdown=failure_breakdown,
            case_results=case_results,
        )

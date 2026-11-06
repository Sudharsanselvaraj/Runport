"""Classification benchmark runner.

Executes through GenericRunner, so the runner guard order is GenericRunner's: authorization (a LiveAuthorization
covering the target is required for every batch, because every case is a provider request), whole-batch privacy
gate (only PUBLIC / SYNTHETIC cases leave the machine), budget preflight, transport, strict validation, persistence
and spend booking on the ledger. This module adds label validation and the PredictionRecord store.
"""

import hashlib
import time
import uuid
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Dict, List, Optional, Sequence

from runport.classification.contracts import ClassificationCase
from runport.classification.records import PredictionRecord, PredictionStore
from runport.classification.validators import validate_classification_output
from runport.core.budget import BudgetService
from runport.core.live_guard import LiveAuthorization, require_live_authorization
from runport.providers.base import BaseProvider, LiveNotAuthorizedError
from runport.schemas.evaluation import DataClassification
from runport.targets.base import CostBasis, TargetStatus

_ELIGIBLE = (DataClassification.PUBLIC, DataClassification.SYNTHETIC)
_RECORD_BASIS = {CostBasis.ACTUAL: "PROVIDER_REPORTED", CostBasis.ESTIMATED: "ESTIMATED_FROM_CATALOG"}


@dataclass
class ClassificationRunSummary:
    run_id: str
    target_id: str
    n_cases: int
    n_ok: int = 0
    n_invalid: int = 0
    n_error: int = 0
    total_spend_usd: Decimal = Decimal("0")


class ClassificationRunner:
    """Orchestrates classification benchmarking under budget and privacy controls."""

    def __init__(
        self,
        provider: BaseProvider,
        budget_service: Optional[BudgetService] = None,
        store: Optional[PredictionStore] = None,
    ):
        self.provider = provider
        self.budget_service = budget_service or BudgetService()
        self.store = store

    def run_batch(
        self,
        cases: Sequence[ClassificationCase],
        target_id: str,
        run_id: Optional[str] = None,
        live_auth: Optional[LiveAuthorization] = None,
        allowed_labels: Optional[List[str]] = None,
        prompt_template: str = "{input}",
    ) -> ClassificationRunSummary:
        from runport.connectors.openrouter import OpenRouterTarget
        from runport.core.approvers import TokenApprover
        from runport.core.workspace import load_workspace_config
        from runport.runs.executor import GenericRunner
        from runport.runs.planner import ExecutionPlan

        # 1. Authorization: every case is a provider request, so a live authorization covering the target is required.
        if live_auth is None:
            barred = next((c for c in cases if c.data_classification not in _ELIGIBLE), None)
            if barred is not None:
                raise LiveNotAuthorizedError(
                    f"Case {barred.case_id} is {barred.data_classification.value}; it may not be sent, and live authorization required for any batch."
                )
            raise LiveNotAuthorizedError(f"Classification batches send provider requests; live authorization required for '{target_id}'.")
        require_live_authorization(live_auth, target_id)

        prompt_hash = f"sha256:{hashlib.sha256(prompt_template.encode()).hexdigest()[:16]}"
        dataset_hash = "synthetic-v1"
        case_dicts: List[Dict[str, Any]] = [
            {"id": c.case_id, "query": prompt_template.format(input=c.input_text), "classification": c.data_classification.value} for c in cases
        ]
        target = OpenRouterTarget(model_id=target_id, adapter=self.provider, system_prompt=None, max_tokens=64)  # type: ignore[arg-type]
        plan = ExecutionPlan(
            plan_id=f"cls-{uuid.uuid4().hex[:8]}",
            target_ids=[target_id],
            dataset_path="classification-batch",
            dataset_hash=hashlib.sha256(repr(case_dicts).encode()).hexdigest(),
            total_cases=len(case_dicts),
            budget_cap_usd=self.budget_service.policy.per_run_ceiling_usd,
            prompt_template_hash=prompt_hash,
            is_live=True,
        )
        runner = GenericRunner(budget_service=self.budget_service, db=self.budget_service.db, workspace=load_workspace_config())
        approver = TokenApprover(token=plan.fingerprint, enabled=True, operator="live_authorization")
        # 2-7: privacy gate, budget preflight, transport, validation, persistence, spend booking.
        run = runner.execute_plan(plan, {target_id: target}, case_dicts, approver=approver)[0]

        r_id = run_id or run.run_id
        summary = ClassificationRunSummary(run_id=r_id, target_id=target_id, n_cases=len(cases), total_spend_usd=run.total_spend_usd)
        for case, res in zip(cases, run.case_results):
            if res.status == TargetStatus.SUCCESS:
                val = validate_classification_output(res.output_text or "", allowed_labels=allowed_labels)
                rec_status = "OK" if val.valid else "INVALID_OUTPUT"
                summary.n_ok += 1 if val.valid else 0
                summary.n_invalid += 0 if val.valid else 1
                label = val.label
            else:
                summary.n_error += 1
                rec_status = "TIMEOUT" if res.status == TargetStatus.TIMEOUT else "ERROR"
                label = None
            basis = _RECORD_BASIS.get(res.cost_basis) if res.cost_usd is not None else None
            rec = PredictionRecord(
                record_id=f"{r_id}:{case.case_id}:{target_id}",
                run_id=r_id,
                case_id=case.case_id,
                task="classification",
                model_key=target_id,
                requested_model_id=target_id,
                prompt_version=prompt_hash,
                dataset_version=dataset_hash,
                status=rec_status,  # type: ignore[arg-type]
                predicted_label=label,
                raw_output=res.output_text,
                prompt_tokens=res.tokens_in,
                completion_tokens=res.tokens_out,
                latency_ms=res.latency_ms,
                actual_cost_usd=res.cost_usd if res.cost_basis == CostBasis.ACTUAL else None,
                estimated_cost_usd=res.cost_usd if res.cost_basis == CostBasis.ESTIMATED else None,
                # The record format keeps cost_usd as a number; an unknown cost is UNAVAILABLE here and UNRESOLVED on the ledger.
                cost_usd=res.cost_usd if (basis and res.cost_usd is not None) else Decimal("0"),
                cost_basis=basis or "UNAVAILABLE",  # type: ignore[arg-type]
                error_message=res.error_message,
                created_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            )
            if self.store:
                self.store.append(rec)
        if run.halted_reason:
            from runport.core.budget import BudgetExceededError
            from runport.providers.base import UsageUnavailableError

            if run.halt_kind == "budget":
                raise BudgetExceededError(run.halted_reason)
            raise UsageUnavailableError(run.halted_reason)
        return summary

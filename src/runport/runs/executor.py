"""Generic benchmark execution engine enforcing the strict runner guard order.

Guard Order:
1. Authorization Check (plan fingerprint + unblock check)
2. Privacy Gate (batch-level forbidden fields / redaction gate)
3. Preflight Budget & Context Check
4. Transport Execution (via Target abstraction)
5. Strict Validation
6. Persistence
7. Spend Booking (booked as UNRESOLVED if cost is unknown/missing)
"""

from decimal import Decimal
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Union

from runport.core.approvers import BaseApprover
from runport.core.budget import BudgetExceededError, BudgetService
from runport.core.workspace import WorkspaceConfig
from runport.providers.base import LiveNotAuthorizedError
from runport.runs.planner import ExecutionPlan
from runport.storage.db import DatabaseManager
from runport.targets.base import CostBasis, Target, TargetResult, TargetStatus


@dataclass
class GenericRunResult:
    """Summary result of a generic execution run."""

    run_id: str
    plan_id: str
    plan_fingerprint: str
    target_id: str
    total_cases: int
    successful_cases: int = 0
    failed_cases: int = 0
    invalid_cases: int = 0
    total_spend_usd: Decimal = Decimal("0")
    mean_latency_ms: float = 0.0
    case_results: List[TargetResult] = field(default_factory=list)


class GenericRunner:
    """Universal benchmark executor adhering strictly to runner guard order."""

    def __init__(
        self,
        budget_service: Optional[BudgetService] = None,
        db: Optional[DatabaseManager] = None,
        workspace: Optional[WorkspaceConfig] = None,
    ):
        self.db = db or DatabaseManager()
        self.budget_service = budget_service or BudgetService(db=self.db)
        self.workspace = workspace or WorkspaceConfig()

    def execute_plan(
        self,
        plan: ExecutionPlan,
        targets: Dict[str, Target],
        cases: Sequence[Dict[str, Any]],
        approver: Optional[BaseApprover] = None,
    ) -> List[GenericRunResult]:
        """Execute a validated execution plan across configured targets."""
        # --- Guard 1: Authorization Check ---
        status = self.budget_service.get_status()
        if plan.is_live and status.unresolved_spend_count > 0:
            raise LiveNotAuthorizedError(
                f"Unresolved spend detected ({status.unresolved_spend_count} transactions). "
                "Live runs are blocked until ledger entries are reconciled via 'runport budget reconcile'."
            )

        if plan.is_live:
            if approver is None:
                raise LiveNotAuthorizedError("Live execution requested but no approver provided.")
            decision = approver.request_approval(
                plan_fingerprint=plan.fingerprint,
                summary_text=f"Plan {plan.plan_id} covering {len(plan.target_ids)} targets.",
                candidate_count=len(plan.target_ids),
            )
            if not decision.approved:
                raise LiveNotAuthorizedError(f"Plan approval rejected by {decision.approver_kind}.")

        # --- Guard 2: Privacy Gate (Whole-batch check) ---
        forbidden = set(self.workspace.telemetry.forbidden_fields)
        for i, c in enumerate(cases):
            for k in c.keys():
                if k.lower() in forbidden:
                    raise ValueError(
                        f"Whole-batch privacy gate rejected case {i} ('{c.get('id', i)}'): forbidden field '{k}' detected before transport execution."
                    )

        # Execute each target
        run_results: List[GenericRunResult] = []

        for target_id in plan.target_ids:
            if target_id not in targets:
                raise ValueError(f"Target '{target_id}' not found in provided targets registry.")

            target = targets[target_id]
            run_id = f"run-{uuid.uuid4().hex[:8]}-{target_id.replace('/', '_')}"
            run_res = GenericRunResult(
                run_id=run_id,
                plan_id=plan.plan_id,
                plan_fingerprint=plan.fingerprint,
                target_id=target_id,
                total_cases=len(cases),
            )

            total_lat = 0.0
            persisted_results: List[Dict[str, Any]] = []

            for case in cases:
                case_id = str(case.get("id") or case.get("case_id") or "case")

                # --- Guard 3: Preflight Budget & Context Check ---
                if plan.is_live:
                    target_pricing = getattr(target, "pricing", None)
                    is_priced = target_pricing is not None and (target_pricing.input_usd_per_1m is not None or target_pricing.fixed_usd_per_request is not None)
                    if not is_priced:
                        if self.workspace.budget.require_priced:
                            raise BudgetExceededError(f"Model/target '{target_id}' has unknown pricing and require_priced is enabled.")
                        # Unknown-price model runs with UNAVAILABLE estimate and requires max_cost_per_case_usd
                        worst_case_estimate = self.workspace.budget.per_case_usd
                        if not worst_case_estimate or worst_case_estimate <= Decimal("0.00"):
                            raise BudgetExceededError(f"Unknown-price target '{target_id}' requires a positive per-case spend cap (max_cost_per_case_usd).")
                    else:
                        assert target_pricing is not None
                        worst_case_estimate = target_pricing.calculate_cost(1000, 500) or self.workspace.budget.per_case_usd

                    ok, msg = self.budget_service.check_spend_permitted(worst_case_estimate)
                    if not ok:
                        raise BudgetExceededError(f"Preflight budget check failed for case '{case_id}': {msg}")

                # --- Guard 4: Transport Execution ---
                t0 = time.perf_counter()
                try:
                    res = target.execute(case)
                except Exception as exc:
                    elapsed_ms = (time.perf_counter() - t0) * 1000.0
                    res = TargetResult(
                        target_id=target_id,
                        status=TargetStatus.FAILED,
                        error_message=str(exc),
                        latency_ms=elapsed_ms,
                        is_replay=not plan.is_live,
                        provenance="REPLAYED" if not plan.is_live else "LIVE",
                    )
                elapsed_ms = res.latency_ms or ((time.perf_counter() - t0) * 1000.0)
                total_lat += elapsed_ms

                # --- Guard 5: Strict Validation ---
                if res.status == TargetStatus.SUCCESS:
                    if res.output_text is None or not str(res.output_text).strip():
                        res.status = TargetStatus.INVALID_OUTPUT
                        res.error_message = "Output text was empty or whitespace."
                        run_res.invalid_cases += 1
                    else:
                        run_res.successful_cases += 1
                else:
                    run_res.failed_cases += 1

                # --- Guard 6: Persistence Data Prep ---
                persisted_results.append(
                    {
                        "result_id": f"res-{uuid.uuid4().hex[:12]}",
                        "run_id": run_id,
                        "case_id": case_id,
                        "prompt": str(case.get("query") or case.get("prompt") or case.get("input") or ""),
                        "expected_answer": str(case.get("expected_answer") or ""),
                        "generated_output": str(res.output_text or ""),
                        "latency_ms": elapsed_ms,
                        "prompt_tokens": res.tokens_in,
                        "completion_tokens": res.tokens_out,
                        "cost_usd": f"{res.cost_usd:.6f}" if res.cost_usd is not None else None,
                        "accuracy": 1.0 if res.status == TargetStatus.SUCCESS else 0.0,
                        "groundedness": 1.0 if res.status == TargetStatus.SUCCESS else 0.0,
                        "format_adherence": 1.0 if res.status != TargetStatus.INVALID_OUTPUT else 0.0,
                        "overall_score": 1.0 if res.status == TargetStatus.SUCCESS else 0.0,
                        "evaluator_notes": res.error_message,
                    }
                )

                # --- Guard 7: Spend Booking ---
                if plan.is_live and not res.is_replay:
                    basis = res.cost_basis.value if isinstance(res.cost_basis, CostBasis) else str(res.cost_basis)
                    if res.cost_usd is not None:
                        self.budget_service.record_spend(
                            transaction_id=f"tx-{uuid.uuid4().hex[:12]}",
                            model_id=target_id,
                            provider=getattr(target, "provider_name", "unknown"),
                            amount_usd=res.cost_usd,
                            description=f"Run {run_id} Case {case_id}",
                            run_id=run_id,
                            is_pilot=True,
                            cost_basis=basis,
                        )
                        run_res.total_spend_usd += res.cost_usd
                    elif basis == CostBasis.UNAVAILABLE.value:
                        # Zero-cost unpriced / local execution: booked as $0.00 with UNAVAILABLE basis
                        self.budget_service.record_spend(
                            transaction_id=f"tx-{uuid.uuid4().hex[:12]}",
                            model_id=target_id,
                            provider=getattr(target, "provider_name", "local"),
                            amount_usd=Decimal("0.000000"),
                            description=f"Run {run_id} Case {case_id} (Local/Unavailable)",
                            run_id=run_id,
                            is_pilot=True,
                            cost_basis=CostBasis.UNAVAILABLE.value,
                        )
                    else:
                        # Billed request with unknown cost -> booked as UNRESOLVED
                        self.budget_service.record_unresolved_spend(
                            transaction_id=f"tx-{uuid.uuid4().hex[:12]}",
                            model_id=target_id,
                            provider=getattr(target, "provider_name", "unknown"),
                            description=f"Run {run_id} Case {case_id} (Unresolved)",
                            run_id=run_id,
                        )

                run_res.case_results.append(res)

            if len(cases) > 0:
                run_res.mean_latency_ms = total_lat / len(cases)

            # Persist run and results (run first for foreign key integrity)
            run_dict = {
                "run_id": run_id,
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "model_id": target_id,
                "dataset_path": plan.dataset_path,
                "total_cases": len(cases),
                "completed_cases": run_res.successful_cases,
                "failed_cases": run_res.failed_cases + run_res.invalid_cases,
                "total_cost_usd": f"{run_res.total_spend_usd:.6f}",
                "mean_latency_ms": run_res.mean_latency_ms,
                "mean_accuracy": run_res.successful_cases / len(cases) if cases else 0.0,
                "mean_groundedness": run_res.successful_cases / len(cases) if cases else 0.0,
                "mean_overall_score": run_res.successful_cases / len(cases) if cases else 0.0,
                "is_dry_run": 1 if not plan.is_live else 0,
                "notes": f"Plan: {plan.plan_id} (Fingerprint: {plan.fingerprint[:12]})",
            }
            self.db.save_evaluation_run(run_dict)
            if persisted_results:
                self.db.save_evaluation_results(persisted_results)

            run_results.append(run_res)

        return run_results

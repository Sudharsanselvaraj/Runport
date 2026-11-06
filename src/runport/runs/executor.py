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
from typing import Any, Callable, Dict, List, Optional, Sequence, Union

from runport.core.approvers import BaseApprover
from runport.core.budget import BudgetExceededError, BudgetService
from runport.core.workspace import WorkspaceConfig
from runport.providers.base import ConfidentialityViolationError, LiveNotAuthorizedError
from runport.runs.planner import ExecutionPlan
from runport.storage.db import DatabaseManager
from runport.targets.base import BillingMode, CostBasis, Target, TargetResult, TargetStatus


def _mean(values: Any) -> Optional[float]:
    measured = [float(v) for v in values if v is not None]
    return round(sum(measured) / len(measured), 4) if measured else None


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
    mean_latency_ms: Optional[float] = None
    skipped_cases: int = 0
    halted_reason: Optional[str] = None
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
        case_scorer: Optional[Callable[[Dict[str, Any], TargetResult], Dict[str, Any]]] = None,
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
        # Confidentiality: only PUBLIC or SYNTHETIC cases may leave this machine. A case without a classification is
        # UNCLASSIFIED and is blocked for any target that is not LOCAL (same rule as the OpenRouter gate).
        remote = [tid for tid in plan.target_ids if getattr(targets.get(tid), "billing", BillingMode.BILLABLE) != BillingMode.LOCAL]
        if remote:
            for i, c in enumerate(cases):
                cls = str(c.get("classification") or "UNCLASSIFIED").upper()
                if cls not in ("PUBLIC", "SYNTHETIC"):
                    raise ConfidentialityViolationError(
                        f"Privacy gate rejected case {i} ('{c.get('id', i)}'): classification {cls} may not be sent to remote target(s) "
                        f"{', '.join(remote)}. Only PUBLIC and SYNTHETIC cases leave this machine."
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
                    billable = getattr(target, "billing", BillingMode.BILLABLE) == BillingMode.BILLABLE
                    if not is_priced:
                        if billable and self.workspace.budget.require_priced:
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
                # Optional scorer (only for successful outputs): returns any of accuracy / groundedness /
                # format_adherence / overall_score / notes. Unscored stays None, never 0.
                scores: Dict[str, Any] = case_scorer(dict(case), res) if (case_scorer and res.status == TargetStatus.SUCCESS) else {}
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
                        # GenericRunner records whether a case completed, not whether it was right.
                        # Correctness is unmeasured here (None), so it is never stored as a score.
                        "accuracy": scores.get("accuracy"),
                        "groundedness": scores.get("groundedness"),
                        "format_adherence": scores.get(
                            "format_adherence", 1.0 if res.status == TargetStatus.SUCCESS else 0.0 if res.status == TargetStatus.INVALID_OUTPUT else None
                        ),
                        "overall_score": scores.get("overall_score"),
                        "evaluator_notes": res.error_message
                        or scores.get("notes")
                        or ("" if scores else "Not scored: apply a scorer from runport.scorers to case_results."),
                    }
                )

                # --- Guard 7: Spend Booking ---
                # Unknown cost never becomes $0.00 for a target that may bill: it is booked UNRESOLVED and the run
                # halts, because unresolved spend blocks live execution until reconciled.
                halt = False
                if plan.is_live and not res.is_replay:
                    basis = res.cost_basis.value if isinstance(res.cost_basis, CostBasis) else str(res.cost_basis)
                    billing = getattr(target, "billing", BillingMode.BILLABLE)
                    # Rejected as unauthorized, or provably never sent: nothing can have been billed.
                    not_billed = res.status == TargetStatus.UNAUTHORIZED or res.request_sent is False
                    if res.cost_usd is not None and basis != CostBasis.UNRESOLVED.value:
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
                    elif billing != BillingMode.BILLABLE or not_billed:
                        # Local, declared-free, or never-billed request: booked as $0.00 with UNAVAILABLE basis
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
                        res.cost_basis = CostBasis.UNRESOLVED
                        halt = True

                run_res.case_results.append(res)
                if halt:
                    run_res.halted_reason = (
                        f"Case '{case_id}' was sent to a billable target and returned no cost; it is booked UNRESOLVED. "
                        "Remaining cases were not sent. Reconcile with 'runport budget reconcile'."
                    )
                    break

            executed = len(run_res.case_results)
            run_res.skipped_cases = len(cases) - executed
            if executed > 0:
                run_res.mean_latency_ms = total_lat / executed

            # Persist run and results (run first for foreign key integrity)
            run_dict = {
                "run_id": run_id,
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "model_id": target_id,
                "dataset_path": plan.dataset_path,
                "total_cases": len(cases),
                "completed_cases": run_res.successful_cases,
                "failed_cases": run_res.failed_cases + run_res.invalid_cases + run_res.skipped_cases,
                "total_cost_usd": f"{run_res.total_spend_usd:.6f}",
                "mean_latency_ms": run_res.mean_latency_ms,
                # Unscored: completion counts live in completed_cases / failed_cases, not in score columns.
                "mean_accuracy": _mean(r["accuracy"] for r in persisted_results),
                "mean_groundedness": _mean(r["groundedness"] for r in persisted_results),
                "mean_overall_score": _mean(r["overall_score"] for r in persisted_results),
                "is_dry_run": 1 if not plan.is_live else 0,
                "notes": f"Plan: {plan.plan_id} (Fingerprint: {plan.fingerprint[:12]})"
                + (f" HALTED: {run_res.halted_reason}" if run_res.halted_reason else ""),
            }
            self.db.save_evaluation_run(run_dict)
            if persisted_results:
                self.db.save_evaluation_results(persisted_results)

            run_results.append(run_res)
            if run_res.halted_reason:
                break  # unresolved spend blocks every remaining target in this plan too

        return run_results

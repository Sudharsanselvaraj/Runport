"""The one guarded execution service for live benchmarks.

Every interface (Web API, SDK, MCP server, CLI target runs) goes through ``ExecutionService``:

    plan()     -> fingerprinted plan + projected worst-case spend + blockers, stored as PENDING. Sends nothing.
    approve()  -> a person approves through an approval channel (CLI phrase, Web UI, CI token). Separate call.
    execute()  -> re-derives the fingerprint from current inputs, atomically consumes the approval, and runs
                  GenericRunner (authorization, privacy gate, budget preflight, transport, validation,
                  persistence, spend booking).

Replay is not handled here: it never touches the network or the live ledger (see runs/replay.py).
"""

from __future__ import annotations

import hashlib
import json
import secrets
from dataclasses import dataclass, field
from decimal import Decimal
from pathlib import Path
from typing import Any, Callable, Dict, List, Mapping, Optional, Sequence, Tuple

from runport.connectors.registry import build_target, check_spec_has_no_literal_secrets, spec_digest
from runport.core.approvers import TokenApprover
from runport.core.budget import BudgetService
from runport.core.config import settings
from runport.core.workspace import WorkspaceConfig, load_workspace_config
from runport.runs.executor import GenericRunner, GenericRunResult
from runport.runs.planner import ExecutionPlan
from runport.services.approvals import ApprovalError, ApprovalRecord, ApprovalStore
from runport.storage.db import DatabaseManager
from runport.targets.base import BillingMode, Target


@dataclass
class PlanSummary:
    plan_id: str
    fingerprint: str
    status: str
    expires_at: float
    target_ids: List[str]
    case_count: int
    dataset_label: str
    projected_max_cost_usd: Optional[Decimal]
    per_target: List[Dict[str, Any]]
    blockers: List[str]
    requested_by: str
    confirmation_phrase: str
    approved_by: Optional[str] = None
    source: Dict[str, Any] = field(default_factory=dict)

    @property
    def is_permitted(self) -> bool:
        return not self.blockers

    def to_dict(self) -> Dict[str, Any]:
        return {
            "plan_id": self.plan_id,
            "plan_fingerprint": self.fingerprint,
            "status": self.status,
            "expires_at": self.expires_at,
            "target_ids": self.target_ids,
            "projected_cases": self.case_count,
            "dataset_name": self.dataset_label,
            "projected_cost_usd": float(self.projected_max_cost_usd) if self.projected_max_cost_usd is not None else None,
            "targets": self.per_target,
            "is_permitted": self.is_permitted,
            "blockers": self.blockers,
            "requested_by": self.requested_by,
            "approved_by": self.approved_by,
            "expected_confirmation_phrase": self.confirmation_phrase,
        }


@dataclass
class ExecutionOutcome:
    plan_id: str
    fingerprint: str
    runs: List[GenericRunResult] = field(default_factory=list)


def _sha(obj: Any) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True, default=str).encode("utf-8")).hexdigest()


def load_dataset_cases(path: Path, sample_size: Optional[int] = None) -> List[Dict[str, Any]]:
    cases: List[Dict[str, Any]] = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#"):
                cases.append(json.loads(line))
    return cases[:sample_size] if sample_size else cases


def resolve_dataset(name: str, root: Optional[Path] = None) -> Path:
    """A dataset file inside <workspace>/data/evaluation, by file name. Refuses anything outside that directory."""
    d_dir = ((root or settings.workspace_root) / "data" / "evaluation").resolve()
    path = (d_dir / name).resolve()
    if d_dir not in path.parents:
        raise ValueError("Dataset name must refer to a file inside data/evaluation.")
    if not path.is_file():
        raise FileNotFoundError(f"Dataset '{name}' not found")
    return path


class ExecutionService:
    def __init__(
        self,
        db: Optional[DatabaseManager] = None,
        workspace: Optional[WorkspaceConfig] = None,
        budget_service: Optional[BudgetService] = None,
        approvals: Optional[ApprovalStore] = None,
    ) -> None:
        if db is None:
            settings.ensure_directories()
            db = DatabaseManager(settings.db_path)
        self.db = db
        self.db.init_db()
        self.workspace = workspace or load_workspace_config()
        self.budget_service = budget_service or BudgetService(db=self.db, policy=self.workspace.budget.to_budget_policy())
        self.approvals = approvals or ApprovalStore(self.db)

    # -- target resolution ----------------------------------------------------------------------

    def workspace_target_specs(self) -> Dict[str, Dict[str, Any]]:
        """Targets declared in the workspace file, as specs (no secret values; only $ENV references)."""
        return {t.id: t.to_spec() for t in self.workspace.targets}

    def resolve(self, target_ids: Sequence[str], *, allow_local_processes: bool = True) -> Tuple[Dict[str, Target], Dict[str, Dict[str, Any]]]:
        """Workspace targets by id; otherwise a catalog model id runs on OpenRouter."""
        declared = self.workspace_target_specs()
        specs: Dict[str, Dict[str, Any]] = {}
        for tid in target_ids:
            spec = declared.get(tid) or {"type": "openrouter", "model": tid}
            check_spec_has_no_literal_secrets(tid, spec)
            specs[tid] = spec
        targets = {tid: build_target(tid, spec, allow_local_processes=allow_local_processes) for tid, spec in specs.items()}
        return targets, specs

    # -- planning --------------------------------------------------------------------------------

    def _plan_object(self, specs: Mapping[str, Mapping[str, Any]], cases: Sequence[Mapping[str, Any]], nonce: str) -> ExecutionPlan:
        return ExecutionPlan(
            plan_id=f"live-{nonce[:8]}",
            target_ids=sorted(specs),
            dataset_path="",
            dataset_hash=_sha({"cases": list(cases), "nonce": nonce}),
            total_cases=len(cases),
            budget_cap_usd=self.workspace.budget.per_run_usd,
            prompt_template_hash=_sha({tid: spec_digest(s) for tid, s in specs.items()}),
            is_live=True,
        )

    def plan(
        self,
        targets: Mapping[str, Target],
        specs: Mapping[str, Mapping[str, Any]],
        cases: Sequence[Mapping[str, Any]],
        *,
        dataset_label: str,
        requested_by: str,
        source: Optional[Dict[str, Any]] = None,
    ) -> PlanSummary:
        """`source` records how to reload the cases later (e.g. dataset name and sample size); it is not trusted:
        execution re-derives the fingerprint from whatever cases it is given."""
        if not cases:
            raise ValueError("A plan needs at least one case.")
        if set(targets) != set(specs):
            raise ValueError("targets and specs must name the same target ids")
        nonce = secrets.token_hex(16)
        plan = self._plan_object(specs, cases, nonce)

        per_case_cap = self.workspace.budget.per_case_usd
        per_target: List[Dict[str, Any]] = []
        total: Optional[Decimal] = Decimal("0")
        blockers: List[str] = []
        for tid in sorted(targets):
            t = targets[tid]
            pricing = t.pricing
            per_case = pricing.calculate_cost(1000, 500) if pricing else None
            billable = t.billing == BillingMode.BILLABLE
            if per_case is None and billable:
                if self.workspace.budget.require_priced:
                    blockers.append(f"'{tid}' has no pricing and require_priced is enabled.")
                # Unknown price on a billable target: reserve the per-case ceiling as the worst case.
                per_case = per_case_cap
            upper = per_case * len(cases) if per_case is not None else None
            if upper is not None and total is not None:
                total += upper
            per_target.append(
                {
                    "target_id": tid,
                    "type": specs[tid].get("type"),
                    "billing": t.billing.value,
                    "priced": pricing is not None,
                    "projected_cost_usd": float(upper) if upper is not None else None,
                    "cost_note": "catalog/configured pricing"
                    if pricing
                    else ("per-case ceiling reserved (price unknown)" if billable else "local or declared free: no spend expected"),
                }
            )

        status = self.budget_service.get_status()
        if status.unresolved_spend_count:
            blockers.append(f"{status.unresolved_spend_count} unresolved ledger entr(y/ies) must be reconciled first ('runport budget reconcile').")
        if total is not None:
            ok, msg = self.budget_service.check_spend_permitted(total)
            if not ok:
                blockers.append(msg)

        summary = {
            "nonce": nonce,
            "target_ids": sorted(targets),
            "specs": {tid: dict(s) for tid, s in specs.items()},
            "case_count": len(cases),
            "cases_digest": _sha(list(cases)),
            "dataset_label": dataset_label,
            "projected_max_cost_usd": str(total) if total is not None else None,
            "per_target": per_target,
            "blockers": blockers,
            "source": source or {},
        }
        rec = self.approvals.register(plan.fingerprint, summary, requested_by=requested_by)
        return self._summary(rec)

    def _summary(self, rec: ApprovalRecord) -> PlanSummary:
        s = rec.summary
        return PlanSummary(
            plan_id=rec.plan_id,
            fingerprint=rec.fingerprint,
            status=rec.status,
            expires_at=rec.expires_at,
            target_ids=list(s["target_ids"]),
            case_count=int(s["case_count"]),
            dataset_label=s["dataset_label"],
            projected_max_cost_usd=Decimal(s["projected_max_cost_usd"]) if s.get("projected_max_cost_usd") is not None else None,
            per_target=list(s["per_target"]),
            blockers=list(s["blockers"]),
            requested_by=rec.requested_by,
            confirmation_phrase=f"RUN LIVE {', '.join(s['target_ids'])} PLAN {rec.fingerprint}",
            approved_by=rec.approved_by,
            source=dict(s.get("source") or {}),
        )

    def get_plan(self, plan_id: str) -> Optional[PlanSummary]:
        rec = self.approvals.get(plan_id)
        return self._summary(rec) if rec else None

    def find_plan(self, fingerprint: str) -> Optional[PlanSummary]:
        rec = self.approvals.find_by_fingerprint(fingerprint)
        return self._summary(rec) if rec else None

    # -- approval (separate operation, human channels only) ------------------------------------

    def approve(self, plan_id: str, fingerprint: str, *, channel: str, approver: str) -> PlanSummary:
        rec = self.approvals.get(plan_id)
        if rec is None:
            raise ApprovalError(f"No plan '{plan_id}'.")
        if rec.summary.get("blockers"):
            raise ApprovalError("Plan has blockers and cannot be approved: " + "; ".join(rec.summary["blockers"]))
        if channel == "local_only" and any(t.get("billing") != BillingMode.LOCAL.value for t in rec.summary.get("per_target", [])):
            raise ApprovalError("local_only approval is only for plans whose every target runs locally; a person must approve this plan.")
        return self._summary(self.approvals.approve(plan_id, fingerprint, channel=channel, approver=approver))

    # -- execution -------------------------------------------------------------------------------

    def execute(
        self,
        plan_id: str,
        targets: Mapping[str, Target],
        specs: Mapping[str, Mapping[str, Any]],
        cases: Sequence[Mapping[str, Any]],
        case_scorer: Optional[Callable[[Dict[str, Any], Any], Dict[str, Any]]] = None,
    ) -> ExecutionOutcome:
        rec = self.approvals.get(plan_id)
        if rec is None:
            raise ApprovalError(f"No plan '{plan_id}'; nothing was sent.")
        plan = self._plan_object(specs, cases, rec.summary["nonce"])
        if plan.fingerprint != rec.fingerprint:
            raise ApprovalError("The targets, cases or caps differ from the approved plan; nothing was sent. Create and approve a new plan.")
        self.approvals.consume(plan_id, rec.fingerprint)  # atomic: exactly one execution per approval
        runner = GenericRunner(budget_service=self.budget_service, db=self.db, workspace=self.workspace)
        approver = TokenApprover(token=rec.fingerprint, enabled=True, operator=rec.approved_by or "unknown")
        runs = runner.execute_plan(plan, dict(targets), [dict(c) for c in cases], approver=approver, case_scorer=case_scorer)
        return ExecutionOutcome(plan_id=plan_id, fingerprint=rec.fingerprint, runs=runs)

    def execute_by_ids(
        self,
        plan_id: str,
        cases: Sequence[Mapping[str, Any]],
        *,
        allow_local_processes: bool = True,
        case_scorer: Optional[Callable[[Dict[str, Any], Any], Dict[str, Any]]] = None,
    ) -> ExecutionOutcome:
        """Execute a plan whose targets are workspace/catalog ids (the stored specs are rebuilt, not trusted blindly)."""
        rec = self.approvals.get(plan_id)
        if rec is None:
            raise ApprovalError(f"No plan '{plan_id}'; nothing was sent.")
        targets, specs = self.resolve(rec.summary["target_ids"], allow_local_processes=allow_local_processes)
        return self.execute(plan_id, targets, specs, cases, case_scorer=case_scorer)


def rubric_case_scorer(case: Dict[str, Any], result: Any) -> Dict[str, Any]:
    """The same rubric BenchmarkRunner applies: lexical accuracy/groundedness against expected_answer, if any."""
    from runport.evaluation.evaluator import RubricEvaluator

    cid = str(case.get("id") or "case")
    score = RubricEvaluator().evaluate(
        score_id=f"score-{cid}", execution_id=f"exec-{cid}", generated_output=result.output_text or "", expected_answer=case.get("expected_answer")
    )
    return {
        "accuracy": score.accuracy,
        "groundedness": score.groundedness,
        "format_adherence": score.format_adherence,
        "overall_score": score.overall_score,
        "notes": score.notes or "",
        # Lexical overlap with the reference answer: a heuristic, never supervised accuracy (AGENTS.md invariant 8).
        "kind": "heuristic",
        "evaluator": "rubric_overlap_v1",
    }

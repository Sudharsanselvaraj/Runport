"""Plans creation and human approval endpoints for REST API v1.

Specification: docs/SDK_API_CONTRACT.md section 2.2.
Invariants:
- A plan sends nothing: it cost-checks, fingerprints, and stores as PENDING.
- Approval requires explicit fingerprint match; agents are forbidden from approving.
"""

from pathlib import Path
from typing import Any, Dict
from fastapi import APIRouter, Depends

from runport.api.v1.auth import (
    SCOPE_PLANS_APPROVE,
    SCOPE_PLANS_CREATE,
    SCOPE_RUNS_READ,
    require_scope,
)
from runport.api.v1.errors import (
    ApprovalInvalidError,
    ForbiddenError,
    InvalidTargetSpecApiError,
    NotFoundError,
    PlanBlockedError,
)
from runport.api.v1.schemas import PlanApproveRequest, PlanCreateRequest, PlanResponse
from runport.connectors.registry import TargetSpecError
from runport.core.config import settings
from runport.core.tenancy import TenantManager
from runport.providers.base import LiveNotAuthorizedError
from runport.services.approvals import ApprovalError
from runport.services.execution import ExecutionService, PlanSummary, load_dataset_cases
from runport.storage.db import DatabaseManager

router = APIRouter(prefix="/plans", tags=["plans"])


def _plan_to_response(plan: PlanSummary) -> PlanResponse:
    return PlanResponse(
        plan_id=plan.plan_id,
        plan_fingerprint=plan.fingerprint,
        status=plan.status,
        expires_at=plan.expires_at,
        target_ids=plan.target_ids,
        case_count=plan.case_count,
        dataset_label=plan.dataset_label,
        projected_max_cost_usd=str(plan.projected_max_cost_usd) if plan.projected_max_cost_usd is not None else None,
        per_target=plan.per_target,
        blockers=plan.blockers,
        confirmation_phrase=plan.confirmation_phrase,
        requested_by=plan.requested_by,
        approved_by=plan.approved_by,
    )


def _dataset_path(name: str) -> Path:
    d_dir = (settings.workspace_root / "data" / "evaluation").resolve()
    p = (d_dir / name).resolve()
    if d_dir not in p.parents:
        raise InvalidTargetSpecApiError("Dataset must reside in data/evaluation.")
    if not p.is_file():
        raise NotFoundError(f"Dataset '{name}' not found.")
    return p


@router.post("", response_model=PlanResponse)
def create_plan(
    req: PlanCreateRequest,
    auth: Dict[str, Any] = Depends(require_scope(SCOPE_PLANS_CREATE)),
) -> PlanResponse:
    """Creates a costed, fingerprinted benchmark execution plan.

    Sends no live requests. Plan remains PENDING until explicitly approved.
    """
    cases = load_dataset_cases(_dataset_path(req.dataset_name), req.sample_size)
    if not cases:
        raise InvalidTargetSpecApiError("Dataset contains 0 valid evaluation cases.")

    service = ExecutionService()
    try:
        targets, specs = service.resolve(req.target_ids)
    except (TargetSpecError, KeyError) as e:
        raise InvalidTargetSpecApiError(f"Cannot resolve target: {e}") from e

    operator_name = auth.get("principal") or auth.get("key_id") or auth.get("name") or "api_v1"
    project_id = auth.get("project_id", "default") if not auth.get("is_master") else "default"
    plan = service.plan(
        targets,
        specs,
        cases,
        dataset_label=req.dataset_name,
        requested_by=operator_name,
        project_id=project_id,
    )
    return _plan_to_response(plan)


@router.get("/{plan_id}", response_model=PlanResponse)
def get_plan(
    plan_id: str,
    auth: Dict[str, Any] = Depends(require_scope(SCOPE_RUNS_READ)),
) -> PlanResponse:
    """Retrieves an execution plan by its plan ID, scoped by project."""
    service = ExecutionService()
    project_id = auth.get("project_id") if not auth.get("is_master") else None
    plan = service.get_plan(plan_id, project_id=project_id)
    if not plan:
        raise NotFoundError(f"Plan '{plan_id}' not found.")
    return _plan_to_response(plan)


@router.post("/{plan_id}/approve", response_model=PlanResponse)
def approve_plan(
    plan_id: str,
    req: PlanApproveRequest,
    auth: Dict[str, Any] = Depends(require_scope(SCOPE_PLANS_APPROVE)),
) -> PlanResponse:
    """Human operator approves a PENDING plan using its cryptographic fingerprint."""
    service = ExecutionService()
    project_id = auth.get("project_id") if not auth.get("is_master") else None
    plan = service.get_plan(plan_id, project_id=project_id)
    if not plan:
        raise NotFoundError(f"Plan '{plan_id}' not found.")

    if plan.fingerprint != req.fingerprint.strip():
        raise ApprovalInvalidError(
            f"Provided fingerprint '{req.fingerprint}' does not match plan '{plan.fingerprint}'.",
            details={"expected_fingerprint": plan.fingerprint, "provided_fingerprint": req.fingerprint},
        )

    if plan.blockers:
        raise PlanBlockedError(
            f"Plan has {len(plan.blockers)} preflight blocker(s) and cannot be approved.",
            details={"blockers": plan.blockers},
        )

    # Derive approver identity from authenticated credentials or authorized approver parameter
    if auth.get("is_master", False) and req.approver:
        approver_identity = req.approver
    else:
        approver_identity = auth.get("principal") or auth.get("key_id") or auth.get("name") or req.approver or "operator"

    # Enforce multi-tenant self-approval prevention on billable plans
    is_billable = False
    if plan.projected_max_cost_usd is not None and float(plan.projected_max_cost_usd) > 0.0:
        is_billable = True

    if not auth.get("is_master", False):
        if plan.requested_by and plan.requested_by == approver_identity:
            target_project_id = auth.get("project_id", "default")
            db = DatabaseManager(settings.db_path)
            db.init_db()
            tm = TenantManager(db=db)
            tenant_ctx = tm.get_context(approver_identity, target_project_id)
            if tenant_ctx:
                can_approve, reason = tenant_ctx.can_approve_plan(plan.requested_by, is_billable)
                if not can_approve:
                    raise ForbiddenError(reason)
            elif is_billable:
                raise ForbiddenError("Self-approval is forbidden on billable plans.")

    try:
        approved = service.approve(
            plan_id,
            req.fingerprint.strip(),
            channel="rest_v1",
            approver=approver_identity,
            project_id=project_id,
        )
    except (LiveNotAuthorizedError, ApprovalError) as e:
        raise ApprovalInvalidError(str(e)) from e

    return _plan_to_response(approved)

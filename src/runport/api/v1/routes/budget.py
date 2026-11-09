"""Budget limits and ledger reconciliation endpoints for REST API v1.

Specification: docs/SDK_API_CONTRACT.md section 2.2.
"""

from decimal import Decimal
from typing import Any, Dict
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from runport.api.v1.auth import SCOPE_BUDGET_READ, SCOPE_BUDGET_RECONCILE, require_scope
from runport.api.v1.errors import NotFoundError
from runport.api.v1.schemas import (
    BudgetPolicyInfo,
    BudgetSpendInfo,
    BudgetStatusResponse,
)
from runport.core.budget import BudgetService
from runport.core.config import settings
from runport.storage.db import DatabaseManager

router = APIRouter(prefix="/budget", tags=["budget"])


class ReconcileRequest(BaseModel):
    transaction_id: str = Field(..., min_length=1, description="Ledger transaction ID to reconcile")
    reconciled_usd: Decimal = Field(..., ge=0, description="Exact reconciled USD cost")
    notes: str = Field(default="", description="Reconciliation notes and verification reference")


@router.get("", response_model=BudgetStatusResponse)
def get_budget_status(auth: Dict[str, Any] = Depends(require_scope(SCOPE_BUDGET_READ))) -> BudgetStatusResponse:
    """Returns local experiment governance ceilings, spent amounts, and unresolved transactions."""
    settings.ensure_directories()
    db = DatabaseManager(settings.db_path)
    db.init_db()
    service = BudgetService(db=db, policy=settings.budget)

    project_id = None if auth.get("is_master") else auth.get("project_id")
    bstatus = service.get_status(project_id=project_id)
    unresolved = db.get_unresolved(project_id=project_id)

    return BudgetStatusResponse(
        policy=BudgetPolicyInfo(
            total_budget_usd=float(settings.budget.total_budget_usd),
            pilot_budget_usd=float(settings.budget.pilot_budget_usd),
            per_run_ceiling_usd=float(settings.budget.per_run_ceiling_usd),
            per_case_ceiling_usd=float(settings.budget.per_case_ceiling_usd),
            require_priced=settings.budget.require_priced,
        ),
        spend=BudgetSpendInfo(
            total_spent_usd=float(bstatus.cumulative_spend_usd),
            pilot_spent_usd=float(bstatus.pilot_spend_usd),
            remaining_total_usd=float(bstatus.remaining_total_usd),
            remaining_pilot_usd=float(bstatus.remaining_pilot_usd),
        ),
        unresolved_count=len(unresolved),
        unresolved_transactions=unresolved,
    )


@router.post("/reconcile", response_model=Dict[str, Any])
def reconcile_transaction(
    req: ReconcileRequest,
    auth: Dict[str, Any] = Depends(require_scope(SCOPE_BUDGET_RECONCILE)),
) -> Dict[str, Any]:
    """Reconciles an unresolved ledger transaction with exact spend."""
    db = DatabaseManager(settings.db_path)
    db.init_db()
    service = BudgetService(db=db, policy=settings.budget)

    # Check if transaction exists and is unresolved within caller's project
    project_id = None if auth.get("is_master") else auth.get("project_id")
    unresolved = db.get_unresolved(project_id=project_id)
    tx_ids = {u["transaction_id"] for u in unresolved}
    if req.transaction_id not in tx_ids:
        raise NotFoundError(f"Unresolved transaction '{req.transaction_id}' not found.")

    service.reconcile_unresolved_spend(
        transaction_id=req.transaction_id,
        actual_usd=req.reconciled_usd,
        notes=req.notes,
        project_id=project_id,
    )
    return {"status": "reconciled", "transaction_id": req.transaction_id, "amount_usd": str(req.reconciled_usd)}

"""Budget tracking and ledger reconciliation API endpoints."""

from decimal import Decimal
from typing import Any, Dict, List
from fastapi import APIRouter
from pydantic import BaseModel

from runport.core.budget import BudgetService
from runport.core.config import settings
from runport.storage.db import DatabaseManager

router = APIRouter(prefix="/budget", tags=["budget"])


class ReconcileRequest(BaseModel):
    transaction_id: str
    reconciled_usd: Decimal
    notes: str = ""


@router.get("", response_model=Dict[str, Any])
def get_budget_status() -> Dict[str, Any]:
    """Returns current budget limits, spent amounts, and unresolved transactions."""
    settings.ensure_directories()
    db = DatabaseManager(settings.db_path)
    db.init_db()
    service = BudgetService(db=db, policy=settings.budget)

    bstatus = service.get_status()
    unresolved = db.get_unresolved()

    recent_txs = []
    with db.get_connection() as conn:
        cur = conn.execute(
            """
            SELECT transaction_id, timestamp, model_id, provider, amount_usd, is_pilot, is_unresolved, cost_basis, description
            FROM budget_ledger
            ORDER BY timestamp DESC
            LIMIT 25
            """
        )
        for r in cur.fetchall():
            recent_txs.append(dict(r))

    return {
        "policy": {
            "total_budget_usd": float(settings.budget.total_budget_usd),
            "pilot_budget_usd": float(settings.budget.pilot_budget_usd),
            "per_run_ceiling_usd": float(settings.budget.per_run_ceiling_usd),
            "per_case_ceiling_usd": float(settings.budget.per_case_ceiling_usd),
            "require_priced": settings.budget.require_priced,
        },
        "spend": {
            "total_spent_usd": float(bstatus.cumulative_spend_usd),
            "pilot_spent_usd": float(bstatus.pilot_spend_usd),
            "remaining_total_usd": float(bstatus.remaining_total_usd),
            "remaining_pilot_usd": float(bstatus.remaining_pilot_usd),
        },
        "unresolved_count": len(unresolved),
        "unresolved_transactions": unresolved,
        "recent_transactions": recent_txs,
    }


@router.post("/reconcile", response_model=Dict[str, Any])
def reconcile_transaction(req: ReconcileRequest) -> Dict[str, Any]:
    """Reconciles an unresolved transaction in the ledger."""
    db = DatabaseManager(settings.db_path)
    db.init_db()
    db.reconcile_transaction(
        transaction_id=req.transaction_id,
        amount_usd=req.reconciled_usd,
        note=req.notes,
    )
    return {"status": "reconciled", "transaction_id": req.transaction_id}

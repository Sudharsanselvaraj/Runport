"""Workspace setup and system configuration API endpoints."""

from typing import Any, Dict, List
from fastapi import APIRouter
from pydantic import BaseModel, Field

from runport import __version__
from runport.core.config import settings
from runport.storage.db import DatabaseManager

router = APIRouter(prefix="/setup", tags=["setup"])


class BudgetPolicySummary(BaseModel):
    total_budget_usd: float
    pilot_budget_usd: float
    per_run_ceiling_usd: float
    per_case_ceiling_usd: float
    require_priced: bool


class SetupResponse(BaseModel):
    app_name: str = "Runport"
    version: str = Field(default_factory=lambda: __version__)
    mode: str = "local_first"
    workspace_root: str
    db_path: str
    db_wal_mode: bool
    budget_policy: BudgetPolicySummary
    forbidden_fields: List[str]
    dataset_schema: Dict[str, Any]


@router.get("", response_model=SetupResponse)
def get_setup_info() -> SetupResponse:
    """Returns workspace paths, spend caps, forbidden fields, and dataset schema."""
    settings.ensure_directories()
    db = DatabaseManager(settings.db_path)
    db.init_db()

    # Query WAL mode from SQLite PRAGMA
    wal_enabled = True
    try:
        with db.get_connection() as conn:
            cur = conn.execute("PRAGMA journal_mode")
            row = cur.fetchone()
            if row and str(row[0]).lower() != "wal":
                wal_enabled = False
    except Exception:
        pass

    from runport.core.workspace import load_workspace_config

    default_forbidden = ["phone", "email", "ssn", "password", "token", "api_key"]
    cfg_telemetry = load_workspace_config().telemetry
    forbidden = cfg_telemetry.forbidden_fields if cfg_telemetry.forbidden_fields else default_forbidden

    schema_info = {
        "required_fields": [
            {"name": "case_id", "type": "string", "description": "Unique evaluation case identifier"},
            {"name": "query", "type": "string", "description": "Input prompt or user query for the target"},
        ],
        "optional_fields": [
            {"name": "ground_truth", "type": "string", "description": "Human-approved annotation for supervised metrics"},
            {"name": "expected_class", "type": "string", "description": "Classification label for F1/Kappa metrics"},
            {"name": "group_id", "type": "string", "description": "Cluster identifier for zero-leakage splits"},
            {"name": "metadata", "type": "object", "description": "Additional test metadata"},
        ],
        "invariants": [
            "Source datasets are hashed (SHA-256) before and after evaluation to guarantee immutability.",
            "Missing telemetry remains None / UNAVAILABLE. Null is not 0.",
            "Agreement is not accuracy; supervised metrics require approved ground truth.",
        ],
    }

    return SetupResponse(
        workspace_root=str(settings.workspace_root),
        db_path=str(settings.db_path),
        db_wal_mode=wal_enabled,
        budget_policy=BudgetPolicySummary(
            total_budget_usd=float(settings.budget.total_budget_usd),
            pilot_budget_usd=float(settings.budget.pilot_budget_usd),
            per_run_ceiling_usd=float(settings.budget.per_run_ceiling_usd),
            per_case_ceiling_usd=float(settings.budget.per_case_ceiling_usd),
            require_priced=settings.budget.require_priced,
        ),
        forbidden_fields=forbidden,
        dataset_schema=schema_info,
    )

"""Benchmark execution planning and fingerprint generation API endpoints."""

from decimal import Decimal
import hashlib
import json
from pathlib import Path
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from runport.core.budget import BudgetService
from runport.core.config import settings
from runport.models.catalog import DEFAULT_PORTFOLIO
from runport.storage.db import DatabaseManager

router = APIRouter(prefix="/plan", tags=["plan"])


class PlanRequest(BaseModel):
    target_ids: List[str] = Field(min_length=1)
    dataset_name: str
    sample_size: Optional[int] = None
    is_pilot: bool = True


@router.post("", response_model=Dict[str, Any])
def create_plan(req: PlanRequest) -> Dict[str, Any]:
    """Generates an honest, costed execution plan and returns a tamper-evident fingerprint."""
    d_dir = settings.workspace_root / "data" / "evaluation"
    dataset_path = (d_dir / req.dataset_name).resolve()
    if not dataset_path.exists():
        raise HTTPException(status_code=404, detail=f"Dataset '{req.dataset_name}' not found")

    case_count = 0
    with open(dataset_path, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip() and not line.startswith("#"):
                case_count += 1

    actual_cases = min(case_count, req.sample_size) if req.sample_size else case_count
    if actual_cases == 0:
        raise HTTPException(status_code=400, detail="Dataset has 0 valid evaluation cases")

    portfolio_map = {m.model_id: m for m in DEFAULT_PORTFOLIO}
    per_target = []
    total_projected_usd = Decimal("0.0000")
    blockers = []

    # Pessimistic estimate: 800 prompt tokens + 250 completion tokens per case
    est_prompt_tokens = 800
    est_completion_tokens = 250

    for tid in req.target_ids:
        model_meta = portfolio_map.get(tid)
        if model_meta:
            in_cost = (Decimal(est_prompt_tokens) / Decimal("1000000")) * model_meta.input_price_per_1m_usd
            out_cost = (Decimal(est_completion_tokens) / Decimal("1000000")) * model_meta.output_price_per_1m_usd
            per_case_est = in_cost + out_cost
            target_est = per_case_est * Decimal(actual_cases)
            total_projected_usd += target_est

            per_target.append({
                "target_id": tid,
                "display_name": model_meta.display_name,
                "input_price_per_1m": float(model_meta.input_price_per_1m_usd),
                "output_price_per_1m": float(model_meta.output_price_per_1m_usd),
                "projected_cost_usd": float(round(target_est, 4)),
            })
        else:
            # Workflow / custom target
            per_target.append({
                "target_id": tid,
                "display_name": tid,
                "input_price_per_1m": None,
                "output_price_per_1m": None,
                "projected_cost_usd": 0.0,
            })

    # Check budget preflight
    settings.ensure_directories()
    db = DatabaseManager(settings.db_path)
    db.init_db()
    service = BudgetService(db=db, policy=settings.budget)
    permitted, reason = service.check_spend_permitted(total_projected_usd, is_pilot=req.is_pilot)
    if not permitted:
        blockers.append(reason)

    # Compute deterministic plan fingerprint
    raw_fingerprint_str = f"{sorted(req.target_ids)}|{req.dataset_name}|{actual_cases}|{total_projected_usd:.6f}"
    fingerprint = hashlib.sha256(raw_fingerprint_str.encode("utf-8")).hexdigest()[:16]

    return {
        "plan_fingerprint": fingerprint,
        "dataset_name": req.dataset_name,
        "projected_cases": actual_cases,
        "projected_cost_usd": float(round(total_projected_usd, 4)),
        "targets": per_target,
        "is_permitted": len(blockers) == 0,
        "blockers": blockers,
        "expected_confirmation_phrase": f"RUN LIVE {', '.join(sorted(req.target_ids))} PLAN {fingerprint}",
    }


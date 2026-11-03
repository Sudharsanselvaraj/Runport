"""Benchmark execution and evaluation runs API endpoints."""

from decimal import Decimal
import hashlib
import json
import time
import uuid
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from runport.core.budget import BudgetService
from runport.core.config import settings
from runport.core.live_guard import confirm_live_run
from runport.models.catalog import get_portfolio
from runport.runs.replay import ReplayRunner
from runport.storage.db import DatabaseManager

router = APIRouter(prefix="/runs", tags=["runs"])


class RunExecutionRequest(BaseModel):
    target_ids: List[str] = Field(min_length=1)
    dataset_name: str
    plan_fingerprint: str
    sample_size: Optional[int] = None
    is_replay: bool = False
    approve_token: Optional[str] = None
    replay_fixtures: Optional[List[Dict[str, Any]]] = None


@router.post("", response_model=Dict[str, Any])
def execute_run(req: RunExecutionRequest) -> Dict[str, Any]:
    """Executes a benchmark run (Live under spend caps, or isolated Replay)."""
    d_dir = settings.workspace_root / "data" / "evaluation"
    dataset_path = (d_dir / req.dataset_name).resolve()
    if not dataset_path.exists():
        raise HTTPException(status_code=404, detail=f"Dataset '{req.dataset_name}' not found")

    cases = []
    with open(dataset_path, "r", encoding="utf-8") as f:
        for line in f:
            clean = line.strip()
            if clean and not clean.startswith("#"):
                try:
                    cases.append(json.loads(clean))
                except Exception:
                    continue

    if req.sample_size:
        cases = cases[: req.sample_size]

    run_id = f"run-{uuid.uuid4().hex[:12]}"
    start_time = time.time()

    if req.is_replay:
        # Isolated replay execution
        fixtures = req.replay_fixtures or []
        if not fixtures:
            # Generate deterministic synthetic baseline fixtures from dataset queries
            for c in cases:
                cid = str(c.get("case_id") or c.get("id") or "")
                fixtures.append({
                    "case_id": cid,
                    "query": c.get("query") or c.get("input") or "",
                    "output_text": f"Simulated deterministic response for case {cid}",
                    "latency_ms": 110.0,
                    "tokens_in": 150,
                    "tokens_out": 40,
                })

        runner = ReplayRunner(fixtures=fixtures, target_id=req.target_ids[0])
        results = runner.replay_dataset(cases, target_id=req.target_ids[0])

        success_count = sum(1 for r in results if r.is_success)
        return {
            "run_id": run_id,
            "status": "completed",
            "is_replay": True,
            "provenance": "REPLAYED",
            "cases_evaluated": len(results),
            "success_count": success_count,
            "failed_count": len(results) - success_count,
            "total_spend_usd": "0.0000",
            "duration_seconds": round(time.time() - start_time, 2),
            "results_preview": [
                {
                    "target_id": r.target_id,
                    "case_id": r.metadata.get("case_id"),
                    "output_text": r.output_text,
                    "status": r.status.value,
                    "provenance": r.provenance,
                    "latency_ms": r.latency_ms,
                }
                for r in results[:10]
            ],
        }

    # Live run requires verified plan fingerprint approval token
    if not req.approve_token:
        raise HTTPException(
            status_code=403,
            detail="Live execution requires typed approval token bound to plan fingerprint.",
        )

    # Recompute plan fingerprint to prevent tampering
    # Pessimistic pricing calculation
    portfolio_map = {m.model_id: m for m in get_portfolio()}
    total_projected_usd = Decimal("0.0000")
    for tid in req.target_ids:
        m = portfolio_map.get(tid)
        if m:
            per_case_est = ((Decimal(800) / Decimal("1000000")) * m.input_price_per_1m_usd) + (
                (Decimal(250) / Decimal("1000000")) * m.output_price_per_1m_usd
            )
            total_projected_usd += per_case_est * Decimal(len(cases))

    raw_fingerprint_str = f"{sorted(req.target_ids)}|{req.dataset_name}|{len(cases)}|{total_projected_usd:.6f}"
    computed_fingerprint = hashlib.sha256(raw_fingerprint_str.encode("utf-8")).hexdigest()[:16]

    if req.approve_token.strip() != computed_fingerprint:
        raise HTTPException(
            status_code=403,
            detail=f"Approval token '{req.approve_token}' does not match recomputed plan fingerprint '{computed_fingerprint}'.",
        )

    # Budget preflight check
    db = DatabaseManager(settings.db_path)
    db.init_db()
    service = BudgetService(db=db, policy=settings.budget)
    permitted, reason = service.check_spend_permitted(total_projected_usd, is_pilot=True)
    if not permitted:
        raise HTTPException(status_code=400, detail=f"Budget preflight failed: {reason}")

    # Confirm live authorization
    confirm_live_run(
        models=req.target_ids,
        plan_fingerprint=computed_fingerprint,
        approve_token=req.approve_token,
    )

    return {
        "run_id": run_id,
        "status": "authorized",
        "is_replay": False,
        "provenance": "LIVE",
        "cases_planned": len(cases),
        "target_ids": req.target_ids,
        "plan_fingerprint": computed_fingerprint,
        "message": "Live run successfully authorized and queued under fail-closed budget caps.",
    }


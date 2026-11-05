"""Benchmark execution and evaluation runs API endpoints."""

import time
import uuid
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from runport.api.routes.plan import dataset_path_for
from runport.connectors.registry import TargetSpecError
from runport.core.budget import BudgetExceededError
from runport.core.config import settings
from runport.providers.base import ConfidentialityViolationError, LiveNotAuthorizedError, scrub_secrets
from runport.runs.replay import ReplayRunner
from runport.services.execution import ExecutionService, load_dataset_cases, rubric_case_scorer
from runport.storage.db import DatabaseManager

router = APIRouter(prefix="/runs", tags=["runs"])


class UIApprovalRequest(BaseModel):
    plan_fingerprint: str
    user: str = "Web User"
    timestamp: str


class UIApprovalResponse(BaseModel):
    status: str
    plan_fingerprint: str
    approval_token: str
    user: str
    timestamp: str


class RunExecutionRequest(BaseModel):
    target_ids: List[str] = Field(min_length=1)
    dataset_name: str
    plan_fingerprint: str
    sample_size: Optional[int] = None
    is_replay: bool = False
    approve_token: Optional[str] = None
    replay_fixtures: Optional[List[Dict[str, Any]]] = None


@router.get("", response_model=List[Dict[str, Any]])
def list_runs(limit: int = 50) -> List[Dict[str, Any]]:
    """Returns historical evaluation runs sorted newest first."""
    db = DatabaseManager(settings.db_path)
    db.init_db()
    return db.get_all_evaluation_runs(limit=limit)


@router.get("/{run_id}", response_model=Dict[str, Any])
def get_run_detail(run_id: str) -> Dict[str, Any]:
    """Retrieves full details and case-level results for a specific run."""
    db = DatabaseManager(settings.db_path)
    db.init_db()
    run = db.get_evaluation_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail=f"Run '{run_id}' not found.")
    results = db.get_evaluation_results_for_run(run_id)
    return {
        "run": run,
        "results": results,
    }


@router.post("/approve", response_model=UIApprovalResponse)
def approve_ui_run(req: UIApprovalRequest) -> UIApprovalResponse:
    """The Web UI approval channel: a person approves a PENDING plan. Returns the plan id to execute with."""
    fp = req.plan_fingerprint.strip()
    if not fp:
        raise HTTPException(status_code=400, detail="Plan fingerprint required.")
    service = ExecutionService()
    plan = service.find_plan(fp)
    if plan is None:
        raise HTTPException(status_code=404, detail="No plan with this fingerprint; create a plan first.")
    try:
        approved = service.approve(plan.plan_id, fp, channel="web_ui", approver=req.user)
    except LiveNotAuthorizedError as e:
        raise HTTPException(status_code=403, detail=str(e)) from e
    return UIApprovalResponse(status="approved", plan_fingerprint=fp, approval_token=approved.plan_id, user=req.user, timestamp=req.timestamp)


@router.post("", response_model=Dict[str, Any])
def execute_run(req: RunExecutionRequest) -> Dict[str, Any]:
    """Executes a benchmark run (Live under spend caps, or isolated Replay)."""
    try:
        cases = load_dataset_cases(dataset_path_for(req.dataset_name), req.sample_size)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Dataset is not valid JSONL: {e}") from e

    run_id = f"run-{uuid.uuid4().hex[:12]}"
    start_time = time.time()

    if req.is_replay:
        # Isolated replay execution
        # Replay only what was recorded: the request's fixtures, or recorded outputs carried by the
        # dataset records themselves. Nothing is generated for cases without a recording (invariant 10).
        fixtures = req.replay_fixtures or cases
        runner = ReplayRunner(fixtures=fixtures, target_id=req.target_ids[0])
        results = runner.replay_dataset(cases, target_id=req.target_ids[0])

        from runport.evaluation.replay_scoring import score_replay_results

        eval_results, agg = score_replay_results(run_id, cases, results)
        success_count = agg["completed_cases"]

        # Persist replay run to database for Results, Compare, and Reports tabs
        db = DatabaseManager(settings.db_path)
        db.init_db()
        from datetime import datetime, timezone

        now_str = datetime.now(timezone.utc).isoformat()
        db.save_evaluation_run(
            {
                "run_id": run_id,
                "timestamp": now_str,
                "model_id": req.target_ids[0],
                "dataset_path": req.dataset_name,
                "total_cases": len(results),
                "completed_cases": success_count,
                "failed_cases": agg["failed_cases"],
                "total_cost_usd": "0.0000",
                "mean_latency_ms": agg["mean_latency_ms"],
                "mean_accuracy": agg["mean_accuracy"],
                "mean_groundedness": agg["mean_groundedness"],
                "mean_overall_score": agg["mean_overall_score"],
                "is_dry_run": True,
                "notes": "Replay benchmark run",
            }
        )
        db.save_evaluation_results(eval_results)
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

    # Live run: an approved plan (approve_token = plan id from POST /api/runs/approve) executed through the shared
    # ExecutionService and GenericRunner. Cases are re-read now; if they changed, the fingerprint no longer matches.
    if not req.approve_token:
        raise HTTPException(status_code=403, detail="Live execution requires an approved plan (POST /api/plan, then POST /api/runs/approve).")
    service = ExecutionService()
    plan = service.get_plan(req.approve_token.strip())
    if plan is None or plan.fingerprint != req.plan_fingerprint.strip():
        raise HTTPException(status_code=403, detail="Approval does not match this plan fingerprint; nothing was sent.")
    try:
        outcome = service.execute_by_ids(plan.plan_id, cases, case_scorer=rubric_case_scorer)
    except LiveNotAuthorizedError as e:
        raise HTTPException(status_code=403, detail=scrub_secrets(str(e))) from e
    except BudgetExceededError as e:
        raise HTTPException(status_code=402, detail=scrub_secrets(str(e))) from e
    except ConfidentialityViolationError as e:
        raise HTTPException(status_code=400, detail=scrub_secrets(str(e))) from e
    except TargetSpecError as e:
        raise HTTPException(status_code=400, detail=scrub_secrets(str(e))) from e

    return {
        "status": "halted" if any(r.halted_reason for r in outcome.runs) else "completed",
        "is_replay": False,
        "provenance": "LIVE",
        "plan_id": outcome.plan_id,
        "plan_fingerprint": outcome.fingerprint,
        "runs": [
            {
                "run_id": r.run_id,
                "target_id": r.target_id,
                "total_cases": r.total_cases,
                "successful_cases": r.successful_cases,
                "failed_cases": r.failed_cases,
                "invalid_cases": r.invalid_cases,
                "skipped_cases": r.skipped_cases,
                "total_spend_usd": str(r.total_spend_usd),
                "mean_latency_ms": r.mean_latency_ms,
                "halted_reason": r.halted_reason,
            }
            for r in outcome.runs
        ],
        "run_id": outcome.runs[0].run_id if outcome.runs else None,
    }

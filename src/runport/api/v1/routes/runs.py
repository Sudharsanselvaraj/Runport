"""Runs and asynchronous jobs execution endpoints for REST API v1.

Specification: docs/SDK_API_CONTRACT.md section 2.2.
"""

from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, Query, Response, status

from runport.api.v1.auth import SCOPE_RUNS_EXECUTE, SCOPE_RUNS_READ, require_scope
from runport.api.v1.errors import ApprovalRequiredError, NotFoundError, PlanBlockedError
from runport.api.v1.jobs import JobManager
from runport.api.v1.routes.plans import _dataset_path
from runport.api.v1.schemas import (
    RunDetailResponse,
    RunJobResponse,
    RunResultItem,
    RunResultsListResponse,
    RunSubmitRequest,
)
from runport.core.config import settings
from runport.services.execution import ExecutionService
from runport.storage.db import DatabaseManager
from runport.traces.domain import Trace
from runport.traces.repository import TraceRepository

router = APIRouter(tags=["runs"])


# =============================================================================
# Asynchronous Job Execution Endpoints
# =============================================================================


@router.post("/plans/{plan_id}/runs", response_model=RunJobResponse, status_code=status.HTTP_202_ACCEPTED)
def submit_plan_run(
    plan_id: str,
    req: RunSubmitRequest = RunSubmitRequest(),
    auth: Dict[str, Any] = Depends(require_scope(SCOPE_RUNS_EXECUTE)),
) -> RunJobResponse:
    """Submits an approved plan for asynchronous background execution.

    Returns HTTP 202 Accepted with a run job tracking handle.
    """
    project_id = auth.get("project_id") if not auth.get("is_master") else None
    service = ExecutionService()
    plan = service.get_plan(plan_id, project_id=project_id)
    if not plan:
        raise NotFoundError(f"Plan '{plan_id}' not found.")

    if plan.status != "APPROVED":
        raise ApprovalRequiredError(
            f"Plan '{plan_id}' is in state '{plan.status}'. It must be approved before execution.",
            details={"plan_id": plan_id, "current_status": plan.status, "fingerprint": plan.fingerprint},
        )

    if plan.blockers:
        raise PlanBlockedError(
            "Plan has unresolved preflight blockers and cannot be executed.",
            details={"blockers": plan.blockers},
        )

    dataset_p = _dataset_path(plan.dataset_label)
    job_mgr = JobManager()
    job = job_mgr.submit_job(
        plan_id=plan_id,
        target_ids=plan.target_ids,
        dataset_path=str(dataset_p),
        sample_size=req.sample_size or plan.case_count,
        requested_by=auth.get("principal") or auth.get("name") or "api_v1",
        project_id=auth.get("project_id", "default"),
        requested_by_key_id=auth.get("key_id"),
    )
    return RunJobResponse(**job)


@router.get("/jobs", response_model=List[RunJobResponse])
def list_jobs(
    limit: int = Query(50, ge=1, le=500),
    auth: Dict[str, Any] = Depends(require_scope(SCOPE_RUNS_READ)),
) -> List[RunJobResponse]:
    """Lists asynchronous execution jobs newest first, scoped by project."""
    project_id = auth.get("project_id") if not auth.get("is_master") else None
    job_mgr = JobManager()
    jobs = job_mgr.list_jobs(limit=limit, project_id=project_id)
    return [RunJobResponse(**j) for j in jobs]


@router.get("/jobs/{job_id}", response_model=RunJobResponse)
def get_job_status(
    job_id: str,
    auth: Dict[str, Any] = Depends(require_scope(SCOPE_RUNS_READ)),
) -> RunJobResponse:
    """Retrieves progress, status, and telemetry for an asynchronous execution job, scoped by project."""
    project_id = auth.get("project_id") if not auth.get("is_master") else None
    job_mgr = JobManager()
    job = job_mgr.get_job(job_id, project_id=project_id)
    return RunJobResponse(**job)


@router.post("/jobs/{job_id}/cancel", response_model=RunJobResponse)
def cancel_job(
    job_id: str,
    auth: Dict[str, Any] = Depends(require_scope(SCOPE_RUNS_EXECUTE)),
) -> RunJobResponse:
    """Cooperatively cancels an active or queued execution job, scoped by project."""
    project_id = auth.get("project_id") if not auth.get("is_master") else None
    job_mgr = JobManager()
    job = job_mgr.cancel_job(job_id, project_id=project_id)
    return RunJobResponse(**job)


# =============================================================================
# Run Inspection & Case Results Endpoints
# =============================================================================


@router.get("/runs", response_model=List[RunDetailResponse])
def list_runs(
    limit: int = Query(50, ge=1, le=500),
    auth: Dict[str, Any] = Depends(require_scope(SCOPE_RUNS_READ)),
) -> List[RunDetailResponse]:
    """Lists historical evaluation runs newest first, scoped by project_id."""
    db = DatabaseManager(settings.db_path)
    db.init_db()
    project_id = auth.get("project_id") if not auth.get("is_master") else None
    runs = db.get_all_evaluation_runs(limit=limit, project_id=project_id)
    return [RunDetailResponse(**r) for r in runs]


@router.get("/runs/{run_id}", response_model=RunDetailResponse)
def get_run_detail(
    run_id: str,
    auth: Dict[str, Any] = Depends(require_scope(SCOPE_RUNS_READ)),
) -> RunDetailResponse:
    """Retrieves metadata and aggregate statistics for a specific evaluation run."""
    db = DatabaseManager(settings.db_path)
    db.init_db()
    project_id = auth.get("project_id") if not auth.get("is_master") else None
    run = db.get_evaluation_run(run_id, project_id=project_id)
    if not run:
        raise NotFoundError(f"Run '{run_id}' not found.")
    return RunDetailResponse(**run)


@router.get("/runs/{run_id}/results", response_model=RunResultsListResponse)
def get_run_results(
    run_id: str,
    auth: Dict[str, Any] = Depends(require_scope(SCOPE_RUNS_READ)),
) -> RunResultsListResponse:
    """Retrieves per-case evaluation results with metrics and scores, scoped by project."""
    db = DatabaseManager(settings.db_path)
    db.init_db()
    project_id = auth.get("project_id") if not auth.get("is_master") else None
    run = db.get_evaluation_run(run_id, project_id=project_id)
    if not run:
        raise NotFoundError(f"Run '{run_id}' not found.")

    raw_results = db.get_evaluation_results_for_run(run_id, project_id=project_id)
    items = []
    for r in raw_results:
        items.append(
            RunResultItem(
                result_id=r.get("result_id"),
                case_id=r["case_id"],
                prompt=r.get("prompt") or "",
                generated_output=r.get("generated_output"),
                latency_ms=r.get("latency_ms"),
                prompt_tokens=r.get("prompt_tokens"),
                completion_tokens=r.get("completion_tokens"),
                cost_usd=r.get("cost_usd"),
                cost_basis=r.get("cost_basis"),
                accuracy=r.get("accuracy"),
                score_kind=r.get("score_kind"),
                trace_id=r.get("trace_id"),
            )
        )
    return RunResultsListResponse(run_id=run_id, total_cases=len(items), results=items)


@router.get("/runs/{run_id}/traces/{case_id}", response_model=Dict[str, Any])
def get_case_trace(
    run_id: str,
    case_id: str,
    auth: Dict[str, Any] = Depends(require_scope(SCOPE_RUNS_READ)),
) -> Dict[str, Any]:
    """Retrieves the full canonical trace and spans for an individual run case, scoped by project."""
    db = DatabaseManager(settings.db_path)
    db.init_db()
    project_id = auth.get("project_id") if not auth.get("is_master") else None
    run = db.get_evaluation_run(run_id, project_id=project_id)
    if not run:
        raise NotFoundError(f"Run '{run_id}' not found.")

    repo = TraceRepository(db=db)
    traces = repo.get_traces_for_case(run_id, case_id, include_spans=True, project_id=project_id)
    if not traces:
        raise NotFoundError(f"No canonical trace found for run '{run_id}', case '{case_id}'.")

    return traces[0].model_dump(mode="json")

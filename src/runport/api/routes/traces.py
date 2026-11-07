"""Canonical traces and spans REST API endpoints."""

from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException, Query

from runport.core.config import settings
from runport.storage.db import DatabaseManager
from runport.traces.repository import TraceRepository

router = APIRouter(tags=["traces"])


@router.get("/traces", response_model=List[Dict[str, Any]])
def list_traces(
    run_id: Optional[str] = Query(None, description="Filter traces by evaluation run ID"),
    case_id: Optional[str] = Query(None, description="Filter traces by benchmark case ID"),
    include_spans: bool = Query(False, description="Whether to include full child span records"),
    limit: int = Query(50, ge=1, le=500, description="Maximum number of traces to return"),
) -> List[Dict[str, Any]]:
    """Retrieves canonical trace trees.

    Filtered by run_id, case_id, or newest first across all runs.
    """
    db = DatabaseManager(settings.db_path)
    db.init_db()
    repo = TraceRepository(db=db)

    if run_id and case_id:
        traces = repo.get_traces_for_case(run_id, case_id, include_spans=include_spans)
    elif run_id:
        traces = repo.get_traces_for_run(run_id, include_spans=include_spans)
    else:
        traces = repo.list_traces(limit=limit, include_spans=include_spans)

    return [t.model_dump(mode="json") for t in traces]


@router.get("/traces/{trace_id}", response_model=Dict[str, Any])
def get_trace_detail(trace_id: str) -> Dict[str, Any]:
    """Retrieves an individual canonical trace with its full span hierarchy."""
    db = DatabaseManager(settings.db_path)
    db.init_db()
    repo = TraceRepository(db=db)

    trace = repo.get_trace(trace_id, include_spans=True)
    if trace is None:
        raise HTTPException(status_code=404, detail=f"Trace '{trace_id}' not found.")

    return trace.model_dump(mode="json")


@router.get("/runs/{run_id}/traces", response_model=List[Dict[str, Any]])
def get_run_traces(run_id: str) -> List[Dict[str, Any]]:
    """Retrieves all traces and spans for a specific evaluation run."""
    db = DatabaseManager(settings.db_path)
    db.init_db()
    repo = TraceRepository(db=db)

    traces = repo.get_traces_for_run(run_id, include_spans=True)
    return [t.model_dump(mode="json") for t in traces]

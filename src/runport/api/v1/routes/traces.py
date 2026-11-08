"""Traces ingestion and retrieval endpoints for REST API v1.

Specification: docs/SDK_API_CONTRACT.md section 2.2.
"""

from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, Query

from runport.api.v1.auth import SCOPE_RUNS_READ, SCOPE_TRACES_WRITE, require_scope
from runport.api.v1.errors import NotFoundError
from runport.core.config import settings
from runport.storage.db import DatabaseManager
from runport.traces.otlp import OtlpExporter, OtlpIngester
from runport.traces.repository import TraceRepository

router = APIRouter(prefix="/traces", tags=["traces"])


@router.get("", response_model=List[Dict[str, Any]])
def list_traces(
    run_id: Optional[str] = Query(None, description="Filter by evaluation run ID"),
    limit: int = Query(50, ge=1, le=500),
    auth: Dict[str, Any] = Depends(require_scope(SCOPE_RUNS_READ)),
) -> List[Dict[str, Any]]:
    """Lists canonical traces across evaluation runs."""
    db = DatabaseManager(settings.db_path)
    db.init_db()
    repo = TraceRepository(db=db)

    if run_id:
        traces = repo.get_traces_for_run(run_id, include_spans=False)
    else:
        traces = repo.list_traces(limit=limit, include_spans=False)

    return [t.model_dump(mode="json") for t in traces]


@router.get("/{trace_id}", response_model=Dict[str, Any])
def get_trace(
    trace_id: str,
    auth: Dict[str, Any] = Depends(require_scope(SCOPE_RUNS_READ)),
) -> Dict[str, Any]:
    """Retrieves full canonical trace with span hierarchy."""
    db = DatabaseManager(settings.db_path)
    db.init_db()
    repo = TraceRepository(db=db)

    trace = repo.get_trace(trace_id, include_spans=True)
    if not trace:
        raise NotFoundError(f"Trace '{trace_id}' not found.")

    return trace.model_dump(mode="json")


@router.get("/{trace_id}/otlp", response_model=Dict[str, Any])
def export_trace_otlp(
    trace_id: str,
    auth: Dict[str, Any] = Depends(require_scope(SCOPE_RUNS_READ)),
) -> Dict[str, Any]:
    """Exports trace in standard OpenTelemetry OTLP JSON format."""
    db = DatabaseManager(settings.db_path)
    db.init_db()
    repo = TraceRepository(db=db)

    trace = repo.get_trace(trace_id, include_spans=True)
    if not trace:
        raise NotFoundError(f"Trace '{trace_id}' not found.")

    return OtlpExporter.export_trace(trace)


@router.post("", response_model=Dict[str, Any])
def ingest_traces(
    payload: Dict[str, Any],
    auth: Dict[str, Any] = Depends(require_scope(SCOPE_TRACES_WRITE)),
) -> Dict[str, Any]:
    """Ingests execution traces in OTLP JSON format into canonical SQLite storage."""
    db = DatabaseManager(settings.db_path)
    db.init_db()
    repo = TraceRepository(db=db)

    traces = OtlpIngester.ingest_to_repository(payload, repo)
    return {
        "status": "ok",
        "traces_ingested": len(traces),
        "spans_ingested": sum(len(t.spans) for t in traces),
        "trace_ids": [t.trace_id for t in traces],
    }

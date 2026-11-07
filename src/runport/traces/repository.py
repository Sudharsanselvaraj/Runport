"""Repository layer for persisting, querying, and managing canonical traces and spans.

Milestone 2 - Phase 1: Persistent Trace & Span Data Models and SQLite Migrations.
"""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from runport.storage.db import DatabaseManager
from runport.traces.domain import Span, SpanStatus, Trace


class TraceRepository:
    """Provides a typed repository interface for canonical traces and spans."""

    def __init__(self, db: Optional[DatabaseManager] = None):
        self.db = db or DatabaseManager()

    def create_trace(self, trace: Trace) -> None:
        """Persists a new trace record. Fails with sqlite3.IntegrityError if duplicate ID."""
        self.db.create_trace(trace)

    def save_trace(self, trace: Trace) -> None:
        """Upserts a trace and any child spans atomically in a single transaction."""
        self.db.save_trace(trace)

    def create_span(self, span: Span) -> None:
        """Persists a single span record. Fails if (trace_id, span_id) already exists."""
        self.db.create_span(span)

    def create_spans(self, spans: List[Span]) -> None:
        """Persists multiple spans in an atomic transaction. Rolls back on error."""
        self.db.create_spans(spans)

    def get_trace(self, trace_id: str, include_spans: bool = True) -> Optional[Trace]:
        """Fetches a trace by ID, optionally including ordered child spans."""
        return self.db.get_trace(trace_id, include_spans=include_spans)

    def get_spans(self, trace_id: str) -> List[Span]:
        """Fetches all spans for a trace ordered chronologically."""
        return self.db.get_spans(trace_id)

    def get_spans_by_parent(self, trace_id: str, parent_span_id: Optional[str]) -> List[Span]:
        """Fetches spans within a trace filtered by immediate parent span."""
        return self.db.get_spans_by_parent(trace_id, parent_span_id)

    def get_traces_for_run(self, run_id: str, include_spans: bool = False) -> List[Trace]:
        """Returns all traces associated with a specific evaluation run."""
        return self.db.get_traces_for_run(run_id, include_spans=include_spans)

    def get_traces_for_case(self, run_id: str, case_id: str, include_spans: bool = False) -> List[Trace]:
        """Returns all traces for a specific run case."""
        return self.db.get_traces_for_case(run_id, case_id, include_spans=include_spans)

    def update_trace_status(
        self,
        trace_id: str,
        status: SpanStatus,
        end_time: Optional[datetime] = None,
    ) -> None:
        """Updates the status and optional completion timestamp of an existing trace."""
        self.db.update_trace_status(trace_id, status, end_time=end_time)

    def update_span_status(
        self,
        trace_id: str,
        span_id: str,
        status: SpanStatus,
        end_time: Optional[datetime] = None,
        error: Optional[str] = None,
    ) -> None:
        """Updates the status, completion timestamp, duration, and error of a span."""
        self.db.update_span_status(trace_id, span_id, status, end_time=end_time, error=error)

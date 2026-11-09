"""Canonical domain models for execution traces and spans.

Milestone 2 - Phase 1: Persistent Trace & Span Data Models.
Enforces strict invariants:
1. 'Null is not 0': missing tokens, latency, or cost remain None.
2. Measured 0 is distinguishable from unavailable telemetry.
3. Timezone-aware UTC datetimes; no fabricated durations from missing timestamps.
4. Valid parent-child relationships and strict cross-trace rejection.
5. Automatic secret and credential scrubbing.
"""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from enum import Enum
import re
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from runport.providers.base import scrub_secrets


def _ensure_utc(val: Any) -> Optional[datetime]:
    """Normalizes any datetime or ISO string to a timezone-aware UTC datetime."""
    if val is None:
        return None
    if isinstance(val, str):
        # Support trailing Z or ISO-8601 strings
        val = datetime.fromisoformat(val.replace("Z", "+00:00"))
    if isinstance(val, datetime):
        if val.tzinfo is None:
            return val.replace(tzinfo=timezone.utc)
        return val.astimezone(timezone.utc)
    raise ValueError(f"Cannot parse UTC datetime from {type(val)}: {val}")


class SpanKind(str, Enum):
    """Canonical categorization for execution spans."""

    LLM = "llm"  # One model invocation
    TOOL = "tool"  # One tool call (MCP or native tool)
    RETRIEVAL = "retrieval"  # Vector / knowledge retrieval
    WORKFLOW_STEP = "workflow_step"  # Node in Dify, LangGraph, n8n, etc.
    AGENT = "agent"  # Autonomous agent or sub-agent invocation
    HANDOFF = "handoff"  # Control handoff between agents
    RERANK = "rerank"  # Reranker evaluation
    ROUTER = "router"  # Routing classification or model router
    OTHER = "other"  # Catch-all for unclassified steps


class SpanStatus(str, Enum):
    """Execution status for a span or trace."""

    OK = "ok"
    ERROR = "error"
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"
    UNSET = "unset"


class SpanEvent(BaseModel):
    """An instant timestamped event within a span (e.g. token chunk, log, state change)."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(..., min_length=1, description="Event name")
    timestamp: datetime = Field(..., description="UTC timestamp of the event")
    attributes: Dict[str, Any] = Field(default_factory=dict, description="Structured attributes")

    @field_validator("timestamp", mode="before")
    @classmethod
    def _validate_timestamp(cls, v: Any) -> datetime:
        dt = _ensure_utc(v)
        if dt is None:
            raise ValueError("SpanEvent timestamp cannot be None")
        return dt

    @field_validator("attributes", mode="before")
    @classmethod
    def _scrub_attributes(cls, v: Any) -> Dict[str, Any]:
        if not isinstance(v, dict):
            return {}
        return scrub_secrets(v)


class Span(BaseModel):
    """A durable canonical span representing an individual unit of work."""

    model_config = ConfigDict(extra="forbid")

    trace_id: str = Field(..., min_length=1, description="Foreign key to the owning Trace")
    span_id: str = Field(..., min_length=1, description="Unique span identifier")
    parent_span_id: Optional[str] = Field(default=None, description="Parent span id within the same trace")
    name: str = Field(..., min_length=1, description="Human-readable span operation name")
    kind: SpanKind = Field(..., description="Canonical span kind category")
    status: SpanStatus = Field(default=SpanStatus.UNSET, description="Execution status")

    start_time: Optional[datetime] = Field(default=None, description="UTC start timestamp")
    end_time: Optional[datetime] = Field(default=None, description="UTC completion timestamp")
    duration_ms: Optional[float] = Field(
        default=None,
        description="Measured duration in milliseconds. None if unmeasured. Never fabricate from missing timestamps.",
    )

    provider: Optional[str] = Field(default=None, description="Provider identifier (e.g. openrouter, dify, anthropic)")
    model: Optional[str] = Field(default=None, description="Model identifier where applicable")

    prompt_tokens: Optional[int] = Field(
        default=None,
        description="Input tokens. None when unmeasured ('Null is not 0'); 0 when legitimately zero.",
    )
    completion_tokens: Optional[int] = Field(
        default=None,
        description="Output tokens. None when unmeasured ('Null is not 0'); 0 when legitimately zero.",
    )
    total_tokens: Optional[int] = Field(
        default=None,
        description="Total tokens. None when unmeasured; 0 when legitimately zero.",
    )

    cost_usd: Optional[str] = Field(
        default=None,
        description="Monetary spend in USD as a decimal string. None if unmeasured/unpriced.",
    )
    cost_basis: Optional[str] = Field(
        default=None,
        description="Spend provenance vocabulary (ACTUAL, ESTIMATED, UNRESOLVED, UNAVAILABLE).",
    )

    attributes: Dict[str, Any] = Field(default_factory=dict, description="Structured attributes (scrubbed)")
    events: List[SpanEvent] = Field(default_factory=list, description="Structured timestamped events")
    error: Optional[str] = Field(default=None, description="Sanitized error details if execution failed")

    attempt: int = Field(default=1, ge=1, description="Retry attempt index (1-based)")
    source: str = Field(default="native", description="Ingestion or execution source")
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Record creation timestamp in UTC",
    )

    @field_validator("start_time", "end_time", "created_at", mode="before")
    @classmethod
    def _validate_timestamps(cls, v: Any) -> Optional[datetime]:
        return _ensure_utc(v)

    @field_validator("duration_ms")
    @classmethod
    def _validate_duration(cls, v: Optional[float]) -> Optional[float]:
        if v is not None and v < 0:
            raise ValueError("duration_ms must be non-negative")
        return v

    @field_validator("prompt_tokens", "completion_tokens", "total_tokens", mode="before")
    @classmethod
    def _validate_tokens(cls, v: Any) -> Optional[int]:
        if v is None:
            return None
        if isinstance(v, bool):
            raise ValueError("Token counts cannot be boolean")
        if not isinstance(v, int):
            try:
                v = int(v)
            except (ValueError, TypeError) as e:
                raise ValueError(f"Invalid integer token count: {v}") from e
        if v < 0:
            raise ValueError("Token counts must be non-negative")
        return v

    @field_validator("cost_usd")
    @classmethod
    def _validate_cost_usd(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        try:
            d = Decimal(str(v).strip())
            if d < Decimal("0"):
                raise ValueError("cost_usd must be non-negative")
            return str(v).strip()
        except InvalidOperation as e:
            raise ValueError(f"Invalid decimal string for cost_usd: {v}") from e

    @field_validator("cost_basis")
    @classmethod
    def _validate_cost_basis(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        allowed = {"ACTUAL", "ESTIMATED", "UNRESOLVED", "UNAVAILABLE"}
        norm = str(v).strip().upper()
        if norm not in allowed:
            raise ValueError(f"cost_basis must be one of {allowed}, got '{v}'")
        return norm

    @field_validator("error", mode="before")
    @classmethod
    def _scrub_error(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        return scrub_secrets(str(v))

    @field_validator("attributes", mode="before")
    @classmethod
    def _scrub_attributes(cls, v: Any) -> Dict[str, Any]:
        if not isinstance(v, dict):
            return {}
        return scrub_secrets(v)

    @model_validator(mode="after")
    def _validate_model_consistency(self) -> Span:
        # Enforce parent_span_id != span_id
        if self.parent_span_id is not None and self.parent_span_id == self.span_id:
            raise ValueError(f"parent_span_id cannot be identical to span_id '{self.span_id}'")

        # Chronological validity
        if self.start_time is not None and self.end_time is not None:
            if self.end_time < self.start_time:
                raise ValueError(f"end_time ({self.end_time}) cannot be earlier than start_time ({self.start_time})")

        # Invariant 3: Do not fabricate duration from missing timestamps.
        # If duration_ms was not provided, but start_time and end_time are both present, compute duration.
        # If either timestamp is missing and duration_ms was not provided, duration_ms remains None.
        if self.duration_ms is None and self.start_time is not None and self.end_time is not None:
            delta_ms = (self.end_time - self.start_time).total_seconds() * 1000.0
            self.duration_ms = max(0.0, round(delta_ms, 3))

        return self


class Trace(BaseModel):
    """A durable canonical trace representing an execution tree for a run case or workflow."""

    model_config = ConfigDict(extra="forbid")

    trace_id: str = Field(..., min_length=1, description="Globally unique trace identifier")
    run_id: Optional[str] = Field(default=None, description="Foreign key to evaluation_runs if run-linked")
    case_id: Optional[str] = Field(default=None, description="Benchmark dataset case ID where applicable")
    target_id: Optional[str] = Field(default=None, description="Target configuration identifier")
    session_id: Optional[str] = Field(default=None, description="Optional interactive or conversational session ID")

    name: str = Field(..., min_length=1, description="Trace name (e.g. test_case_01 or pipeline name)")
    status: SpanStatus = Field(default=SpanStatus.UNSET, description="Overall execution status")

    start_time: Optional[datetime] = Field(default=None, description="UTC trace start timestamp")
    end_time: Optional[datetime] = Field(default=None, description="UTC trace completion timestamp")

    attributes: Dict[str, Any] = Field(default_factory=dict, description="Trace-level metadata (scrubbed)")
    schema_version: int = Field(default=1, description="Schema revision version")

    spans: List[Span] = Field(default_factory=list, description="Ordered child spans belonging to this trace")
    source: str = Field(default="native", description="Ingestion or execution source")
    source_ref: Optional[str] = Field(default=None, description="External reference (e.g. OTel or Langfuse ID)")
    project_id: str = Field(default="default", description="Project ownership identifier")
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Record creation timestamp in UTC",
    )

    @field_validator("start_time", "end_time", "created_at", mode="before")
    @classmethod
    def _validate_timestamps(cls, v: Any) -> Optional[datetime]:
        return _ensure_utc(v)

    @field_validator("attributes", mode="before")
    @classmethod
    def _scrub_attributes(cls, v: Any) -> Dict[str, Any]:
        if not isinstance(v, dict):
            return {}
        return scrub_secrets(v)

    @model_validator(mode="after")
    def _validate_trace(self) -> Trace:
        if self.start_time is not None and self.end_time is not None:
            if self.end_time < self.start_time:
                raise ValueError(f"end_time ({self.end_time}) cannot be earlier than start_time ({self.start_time})")

        if self.spans:
            self.validate_hierarchy()

        return self

    def validate_hierarchy(self) -> None:
        """Validates that all spans belong to this trace, have unique IDs, and form an acyclic tree."""
        span_ids = set()
        for span in self.spans:
            # Enforce cross-trace isolation
            if span.trace_id != self.trace_id:
                raise ValueError(
                    f"Cross-trace span rejected: span '{span.span_id}' has trace_id '{span.trace_id}', which does not match trace '{self.trace_id}'"
                )
            # Enforce unique span IDs
            if span.span_id in span_ids:
                raise ValueError(f"Duplicate span_id '{span.span_id}' detected in trace '{self.trace_id}'")
            span_ids.add(span.span_id)

        # Enforce valid parent references
        parent_map: Dict[str, Optional[str]] = {}
        for span in self.spans:
            parent_map[span.span_id] = span.parent_span_id
            if span.parent_span_id is not None:
                if span.parent_span_id not in span_ids:
                    raise ValueError(f"Span '{span.span_id}' references unknown parent '{span.parent_span_id}' in trace '{self.trace_id}'")

        # Cycle detection
        for span_id in span_ids:
            visited = set()
            curr: Optional[str] = span_id
            while curr is not None:
                if curr in visited:
                    raise ValueError(f"Cyclic parent-child span relationship detected involving span '{curr}'")
                visited.add(curr)
                curr = parent_map.get(curr)

    def add_span(self, span: Span) -> None:
        """Safely attaches a span to this trace, re-validating hierarchy."""
        if span.trace_id != self.trace_id:
            raise ValueError(f"Cannot add span '{span.span_id}' with trace_id '{span.trace_id}' to trace '{self.trace_id}'")
        self.spans.append(span)
        self.validate_hierarchy()

    def get_span(self, span_id: str) -> Optional[Span]:
        """Finds a span by ID within this trace."""
        for s in self.spans:
            if s.span_id == span_id:
                return s
        return None

    def get_root_spans(self) -> List[Span]:
        """Returns all top-level root spans in this trace."""
        return [s for s in self.spans if s.parent_span_id is None]

    def get_child_spans(self, parent_span_id: str) -> List[Span]:
        """Returns all immediate child spans of the specified parent span."""
        return [s for s in self.spans if s.parent_span_id == parent_span_id]

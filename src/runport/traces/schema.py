"""Canonical trace schema re-exports.

Provides backward and design-document compatibility for `runport.traces.schema`.
All models are defined in `runport.traces.domain`.
"""

from runport.traces.domain import (
    Span,
    SpanEvent,
    SpanKind,
    SpanStatus,
    Trace,
)

__all__ = [
    "Span",
    "SpanEvent",
    "SpanKind",
    "SpanStatus",
    "Trace",
]

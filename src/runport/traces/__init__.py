"""Traces package for canonical execution tracing, RAG diagnostics, and span persistence."""

from runport.traces.analyzer import TraceDiagnosticAnalyzer
from runport.traces.domain import (
    Span,
    SpanEvent,
    SpanKind,
    SpanStatus,
    Trace,
)
from runport.traces.importer import TraceImporter
from runport.traces.models import (
    DiagnosisHypothesis,
    FailureCategory,
    ObservationSpan,
    TraceDiagnosticReport,
    TraceRecord,
)
from runport.traces.reporter import DiagnosticReporter
from runport.traces.repository import TraceRepository
from runport.traces.otlp import OtlpIngester, OtlpExporter
from runport.traces.langfuse import LangfuseExporter, LangfuseIngester

__all__ = [
    "TraceImporter",
    "TraceDiagnosticAnalyzer",
    "DiagnosticReporter",
    "FailureCategory",
    "ObservationSpan",
    "TraceRecord",
    "DiagnosisHypothesis",
    "TraceDiagnosticReport",
    "Span",
    "SpanEvent",
    "SpanKind",
    "SpanStatus",
    "Trace",
    "TraceRepository",
    "OtlpIngester",
    "OtlpExporter",
    "LangfuseExporter",
    "LangfuseIngester",
]

"""Unit tests for Milestone 2 - Phase 5: OpenTelemetry / OpenInference Interoperability & OTLP Trace Export.

Tests:
1. Ingestion of OpenTelemetry GenAI semantic convention traces.
2. Ingestion of OpenInference agent/tool/retriever/LLM hierarchies.
3. Strict enforcement of 'Null is not 0' invariant (missing telemetry stays None).
4. Automatic secret and credential scrubbing during OTLP ingestion.
5. Canonical Trace -> OTLP Export -> OTLP Ingest round-trip fidelity.
6. REST API endpoints (POST /api/traces/otlp, POST /api/v1/traces/otlp, GET /api/traces/{trace_id}/otlp).
7. Typer CLI commands (`runport import-otlp`, `runport export-otlp`).
"""

from datetime import datetime, timezone, timedelta
import json
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from typer.testing import CliRunner

from runport.api.app import create_app
from runport.cli import app as cli_app
from runport.core.config import settings
from runport.storage.db import DatabaseManager
from runport.traces.domain import (
    Span,
    SpanEvent,
    SpanKind,
    SpanStatus,
    Trace,
)
from runport.traces.otlp import (
    OtlpExporter,
    OtlpIngester,
    parse_otlp_attributes,
    parse_unix_nano,
    datetime_to_unix_nano,
)
from runport.traces.repository import TraceRepository


@pytest.fixture
def test_db(tmp_path: Path, monkeypatch):
    """Sets up an isolated SQLite database for testing."""
    db_file = tmp_path / "otlp_traces.db"
    monkeypatch.setattr(type(settings), "db_path", property(lambda self: db_file))
    db = DatabaseManager(db_file)
    db.init_db()

    # Create linked evaluation run for foreign key integrity
    t0 = datetime(2026, 11, 7, 10, 0, 0, tzinfo=timezone.utc)
    db.save_evaluation_run(
        {
            "run_id": "run-otlp-100",
            "timestamp": t0.isoformat(),
            "model_id": "openai/gpt-4o",
            "dataset_path": "eval.jsonl",
            "total_cases": 1,
            "completed_cases": 1,
            "failed_cases": 0,
            "duration_ms": 500.0,
            "total_cost_usd": "0.0001",
        }
    )
    return db


# =============================================================================
# 1. OpenTelemetry GenAI Semantic Convention Ingestion
# =============================================================================


def test_ingest_genai_otlp_payload():
    """Validates ingestion of standard OTLP JSON with GenAI semantic conventions."""
    t_start = 1731000000000000000
    t_end = 1731000000350000000

    otlp_payload = {
        "resourceSpans": [
            {
                "resource": {
                    "attributes": [
                        {"key": "service.name", "value": {"stringValue": "rag-eval-service"}},
                        {"key": "service.version", "value": {"stringValue": "1.2.0"}},
                    ]
                },
                "scopeSpans": [
                    {
                        "scope": {"name": "genai.tracer", "version": "0.1.0"},
                        "spans": [
                            {
                                "traceId": "4bf92f3577b34da6a3ce929d0e0e4736",
                                "spanId": "00f067aa0ba902b7",
                                "name": "chat_completion",
                                "kind": 3,
                                "startTimeUnixNano": str(t_start),
                                "endTimeUnixNano": str(t_end),
                                "attributes": [
                                    {"key": "gen_ai.system", "value": {"stringValue": "openai"}},
                                    {"key": "gen_ai.request.model", "value": {"stringValue": "gpt-4o"}},
                                    {"key": "gen_ai.response.model", "value": {"stringValue": "gpt-4o-2024-05-13"}},
                                    {"key": "gen_ai.usage.input_tokens", "value": {"intValue": 150}},
                                    {"key": "gen_ai.usage.output_tokens", "value": {"intValue": 45}},
                                    {"key": "gen_ai.operation.name", "value": {"stringValue": "chat"}},
                                    {"key": "runport.cost_usd", "value": {"stringValue": "0.00045"}},
                                    {"key": "runport.cost_basis", "value": {"stringValue": "ESTIMATED"}},
                                ],
                                "events": [
                                    {
                                        "timeUnixNano": str(t_start + 100000000),
                                        "name": "first_token_received",
                                        "attributes": [{"key": "ttft_ms", "value": {"doubleValue": 100.0}}],
                                    }
                                ],
                                "status": {"code": 1, "message": ""},
                            }
                        ],
                    }
                ],
            }
        ]
    }

    traces = OtlpIngester.parse_payload(otlp_payload)
    assert len(traces) == 1
    trace = traces[0]

    assert trace.trace_id == "4bf92f3577b34da6a3ce929d0e0e4736"
    assert trace.name == "chat_completion"
    assert trace.status == SpanStatus.OK
    assert trace.attributes["service.name"] == "rag-eval-service"
    assert len(trace.spans) == 1

    span = trace.spans[0]
    assert span.span_id == "00f067aa0ba902b7"
    assert span.kind == SpanKind.LLM
    assert span.status == SpanStatus.OK
    assert span.provider == "openai"
    assert span.model == "gpt-4o-2024-05-13"
    assert span.prompt_tokens == 150
    assert span.completion_tokens == 45
    assert span.total_tokens is None  # 'Null is not 0': total wasn't reported, not fabricated
    assert span.duration_ms == 350.0
    assert span.cost_usd == "0.00045"
    assert span.cost_basis == "ESTIMATED"
    assert len(span.events) == 1
    assert span.events[0].name == "first_token_received"


# =============================================================================
# 2. OpenInference Agent & Multi-Span Hierarchy Ingestion
# =============================================================================


def test_ingest_openinference_agent_hierarchy():
    """Validates ingestion of an OpenInference trace containing AGENT -> RETRIEVER & TOOL hierarchy."""
    t0 = 1731000000000000000
    t_agent_end = 1731000001000000000
    t_ret_end = 1731000000300000000
    t_tool_start = 1731000000350000000
    t_tool_end = 1731000000800000000

    otlp_payload = {
        "resourceSpans": [
            {
                "scopeSpans": [
                    {
                        "spans": [
                            # Root Agent span
                            {
                                "traceId": "trace-agent-001",
                                "spanId": "span-agent-root",
                                "name": "ResearchAgent",
                                "kind": 1,
                                "startTimeUnixNano": str(t0),
                                "endTimeUnixNano": str(t_agent_end),
                                "attributes": [
                                    {"key": "openinference.span.kind", "value": {"stringValue": "AGENT"}},
                                    {"key": "agent.name", "value": {"stringValue": "researcher"}},
                                ],
                                "status": {"code": 1},
                            },
                            # Child Retriever span
                            {
                                "traceId": "trace-agent-001",
                                "spanId": "span-retriever",
                                "parentSpanId": "span-agent-root",
                                "name": "ChromaDBQuery",
                                "kind": 3,
                                "startTimeUnixNano": str(t0),
                                "endTimeUnixNano": str(t_ret_end),
                                "attributes": [
                                    {"key": "openinference.span.kind", "value": {"stringValue": "RETRIEVER"}},
                                    {"key": "retrieval.documents", "value": {"stringValue": "doc1, doc2"}},
                                ],
                                "status": {"code": 1},
                            },
                            # Child Tool span
                            {
                                "traceId": "trace-agent-001",
                                "spanId": "span-tool",
                                "parentSpanId": "span-agent-root",
                                "name": "Calculator",
                                "kind": 3,
                                "startTimeUnixNano": str(t_tool_start),
                                "endTimeUnixNano": str(t_tool_end),
                                "attributes": [
                                    {"key": "openinference.span.kind", "value": {"stringValue": "TOOL"}},
                                    {"key": "tool.name", "value": {"stringValue": "multiply"}},
                                    {"key": "tool.parameters", "value": {"stringValue": '{"a": 6, "b": 7}'}},
                                ],
                                "status": {"code": 1},
                            },
                        ]
                    }
                ]
            }
        ]
    }

    traces = OtlpIngester.parse_payload(otlp_payload)
    assert len(traces) == 1
    trace = traces[0]

    assert trace.trace_id == "trace-agent-001"
    assert len(trace.spans) == 3

    kinds = {s.span_id: s.kind for s in trace.spans}
    assert kinds["span-agent-root"] == SpanKind.AGENT
    assert kinds["span-retriever"] == SpanKind.RETRIEVAL
    assert kinds["span-tool"] == SpanKind.TOOL

    # Check parent-child relationships
    parents = {s.span_id: s.parent_span_id for s in trace.spans}
    assert parents["span-agent-root"] is None
    assert parents["span-retriever"] == "span-agent-root"
    assert parents["span-tool"] == "span-agent-root"


# =============================================================================
# 3. Secret Scrubbing & Invariant Enforcement
# =============================================================================


def test_secret_scrubbing_on_otlp_ingest():
    """Confirms that API keys, bearer tokens, and credentials in OTLP payloads are scrubbed."""
    otlp_payload = {
        "resourceSpans": [
            {
                "scopeSpans": [
                    {
                        "spans": [
                            {
                                "traceId": "sec-trace-1",
                                "spanId": "sec-span-1",
                                "name": "call_external_api",
                                "kind": 3,
                                "startTimeUnixNano": "1731000000000000000",
                                "endTimeUnixNano": "1731000000100000000",
                                "attributes": [
                                    {"key": "authorization", "value": {"stringValue": "Bearer sk-proj-1234567890abcdef"}},
                                    {"key": "api_key", "value": {"stringValue": "sk-ant-api03-abcdef123456789"}},
                                    {"key": "prompt", "value": {"stringValue": "Authorization failed with key sk-proj-1234567890abcdef"}},
                                ],
                                "status": {
                                    "code": 2,
                                    "message": "Unauthorized: invalid secret key sk-proj-1234567890abcdef",
                                },
                            }
                        ]
                    }
                ]
            }
        ]
    }

    traces = OtlpIngester.parse_payload(otlp_payload)
    span = traces[0].spans[0]

    assert "sk-proj-1234567890abcdef" not in str(span.attributes)
    assert "sk-ant-api03" not in str(span.attributes)
    assert span.error is not None
    assert "sk-proj-1234567890abcdef" not in span.error
    assert "[REDACTED_API_KEY]" in span.error or "[REDACTED" in span.error


def test_null_is_not_zero_invariant_in_otlp():
    """Unmeasured tokens, cost, and duration MUST remain None, never coerced to 0."""
    otlp_payload = {
        "resourceSpans": [
            {
                "scopeSpans": [
                    {
                        "spans": [
                            {
                                "traceId": "null-trace-1",
                                "spanId": "null-span-1",
                                "name": "unmeasured_llm",
                                "kind": 3,
                                # No timestamps provided
                                "attributes": [
                                    {"key": "gen_ai.system", "value": {"stringValue": "custom-local"}},
                                    # No tokens or cost
                                ],
                                "status": {"code": 1},
                            }
                        ]
                    }
                ]
            }
        ]
    }

    traces = OtlpIngester.parse_payload(otlp_payload)
    span = traces[0].spans[0]

    assert span.prompt_tokens is None
    assert span.completion_tokens is None
    assert span.total_tokens is None
    assert span.cost_usd is None
    assert span.cost_basis is None
    assert span.duration_ms is None


# =============================================================================
# 4. Canonical Trace -> OTLP Export -> Ingest Round-Trip Fidelity
# =============================================================================


def test_round_trip_otlp_export_and_ingest():
    """Validates that a canonical Trace exports to standard OTLP and re-ingests with fidelity."""
    t0 = datetime(2026, 11, 7, 14, 0, 0, tzinfo=timezone.utc)
    t1 = t0 + timedelta(milliseconds=250)

    span = Span(
        trace_id="tr-rt-test",
        span_id="sp-rt-root",
        name="llm_roundtrip",
        kind=SpanKind.LLM,
        status=SpanStatus.OK,
        start_time=t0,
        end_time=t1,
        duration_ms=250.0,
        provider="anthropic",
        model="claude-3-5-haiku",
        prompt_tokens=85,
        completion_tokens=32,
        total_tokens=117,
        cost_usd="0.000125",
        cost_basis="ACTUAL",
        attributes={"temperature": 0.2},
    )

    trace = Trace(
        trace_id="tr-rt-test",
        run_id="run-otlp-100",
        case_id="case-001",
        name="roundtrip_trace",
        status=SpanStatus.OK,
        start_time=t0,
        end_time=t1,
        spans=[span],
    )

    # 1. Export to OTLP JSON dictionary
    otlp_dict = OtlpExporter.export_trace(trace)
    assert "resourceSpans" in otlp_dict
    assert len(otlp_dict["resourceSpans"]) == 1

    # 2. Ingest back from OTLP dictionary
    reingested_traces = OtlpIngester.parse_payload(otlp_dict)
    assert len(reingested_traces) == 1
    re_trace = reingested_traces[0]

    assert re_trace.trace_id == "tr-rt-test"
    assert len(re_trace.spans) == 1
    re_span = re_trace.spans[0]

    assert re_span.span_id == "sp-rt-root"
    assert re_span.kind == SpanKind.LLM
    assert re_span.status == SpanStatus.OK
    assert re_span.provider == "anthropic"
    assert re_span.model == "claude-3-5-haiku"
    assert re_span.prompt_tokens == 85
    assert re_span.completion_tokens == 32
    assert re_span.duration_ms == 250.0
    assert re_span.cost_usd == "0.000125"
    assert re_span.cost_basis == "ACTUAL"


# =============================================================================
# 5. REST API Endpoints Tests
# =============================================================================


def test_api_ingest_otlp(test_db: DatabaseManager):
    """Tests POST /api/traces/otlp endpoint."""
    app = create_app()
    client = TestClient(app)

    payload = {
        "resourceSpans": [
            {
                "scopeSpans": [
                    {
                        "spans": [
                            {
                                "traceId": "api-otlp-trace-1",
                                "spanId": "api-otlp-span-1",
                                "name": "api_test",
                                "kind": 1,
                                "attributes": [
                                    {"key": "openinference.span.kind", "value": {"stringValue": "AGENT"}},
                                    {"key": "runport.run_id", "value": {"stringValue": "run-otlp-100"}},
                                ],
                                "status": {"code": 1},
                            }
                        ]
                    }
                ]
            }
        ]
    }

    res = client.post("/api/traces/otlp", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "ok"
    assert data["traces_ingested"] == 1
    assert data["spans_ingested"] == 1
    assert "api-otlp-trace-1" in data["trace_ids"]


def test_api_export_trace_otlp(test_db: DatabaseManager):
    """Tests GET /api/traces/{trace_id}/otlp endpoint."""
    repo = TraceRepository(test_db)
    t0 = datetime(2026, 11, 7, 12, 0, 0, tzinfo=timezone.utc)
    span = Span(
        trace_id="tr-api-export-1",
        span_id="sp-1",
        name="test_step",
        kind=SpanKind.TOOL,
        status=SpanStatus.OK,
        start_time=t0,
    )
    trace = Trace(
        trace_id="tr-api-export-1",
        run_id="run-otlp-100",
        name="api_export_test",
        status=SpanStatus.OK,
        start_time=t0,
        spans=[span],
    )
    repo.save_trace(trace)

    app = create_app()
    client = TestClient(app)

    # Found
    res = client.get("/api/traces/tr-api-export-1/otlp")
    assert res.status_code == 200
    data = res.json()
    assert "resourceSpans" in data
    assert len(data["resourceSpans"]) == 1

    # 404
    res_404 = client.get("/api/traces/non-existent-trace/otlp")
    assert res_404.status_code == 404


# =============================================================================
# 6. Typer CLI Commands Tests
# =============================================================================


def test_cli_import_and_export_otlp(test_db: DatabaseManager, tmp_path: Path):
    """Tests `runport import-otlp` and `runport export-otlp` CLI commands."""
    otlp_payload = {
        "resourceSpans": [
            {
                "scopeSpans": [
                    {
                        "spans": [
                            {
                                "traceId": "cli-trace-1",
                                "spanId": "cli-span-1",
                                "name": "cli_llm_step",
                                "kind": 3,
                                "attributes": [
                                    {"key": "openinference.span.kind", "value": {"stringValue": "LLM"}},
                                    {"key": "runport.run_id", "value": {"stringValue": "run-otlp-100"}},
                                ],
                                "status": {"code": 1},
                            }
                        ]
                    }
                ]
            }
        ]
    }

    # Write fixture file
    otlp_file = tmp_path / "sample_otlp.json"
    otlp_file.write_text(json.dumps(otlp_payload), encoding="utf-8")

    runner = CliRunner()

    # 1. Import via CLI
    res_import = runner.invoke(cli_app, ["import-otlp", str(otlp_file)])
    assert res_import.exit_code == 0
    assert "Successfully ingested 1 trace(s)" in res_import.stdout

    # 2. Export via CLI to file
    out_file = tmp_path / "exported_otlp.json"
    res_export = runner.invoke(cli_app, ["export-otlp", "cli-trace-1", "-o", str(out_file)])
    assert res_export.exit_code == 0
    assert out_file.exists()

    exported_content = json.loads(out_file.read_text(encoding="utf-8"))
    assert "resourceSpans" in exported_content


def test_empty_and_orphan_otlp_payload():
    """Validates resilience against empty payloads and orphan parent references."""
    # Empty
    assert OtlpIngester.parse_payload({}) == []
    assert OtlpIngester.parse_payload({"resourceSpans": []}) == []

    # Orphan parent
    payload = {
        "resourceSpans": [
            {
                "scopeSpans": [
                    {
                        "spans": [
                            {
                                "traceId": "orphan-trace-1",
                                "spanId": "orphan-span-1",
                                "parentSpanId": "missing-parent-99",
                                "name": "orphan_step",
                                "kind": 1,
                                "status": {"code": 1},
                            }
                        ]
                    }
                ]
            }
        ]
    }
    traces = OtlpIngester.parse_payload(payload)
    assert len(traces) == 1
    # Orphan parent was safely cleared
    assert traces[0].spans[0].parent_span_id is None


def test_api_v1_otlp_alias(test_db: DatabaseManager):
    """Tests the /api/v1/traces/otlp alias route."""
    app = create_app()
    client = TestClient(app)

    payload = {
        "resourceSpans": [
            {
                "scopeSpans": [
                    {
                        "spans": [
                            {
                                "traceId": "v1-trace-1",
                                "spanId": "v1-span-1",
                                "name": "v1_test",
                                "kind": 1,
                                "attributes": [
                                    {"key": "runport.run_id", "value": {"stringValue": "run-otlp-100"}},
                                ],
                                "status": {"code": 1},
                            }
                        ]
                    }
                ]
            }
        ]
    }

    res = client.post("/api/v1/traces/otlp", json=payload)
    assert res.status_code == 200
    assert res.json()["status"] == "ok"

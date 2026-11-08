"""Unit tests for Milestone 5 - Task 5.2: Bidirectional Langfuse Interoperability.

Tests:
1. Export of canonical Trace & Spans to Langfuse v2 batch ingestion format (/api/public/ingestion).
2. Export of hierarchical trace detail for Langfuse API compatibility.
3. Ingestion of Langfuse batch payloads and trace exports into canonical Runport Traces.
4. Strict enforcement of 'Null is not 0' invariant across usage and cost metrics.
5. Zero secret leakage: automatic scrubbing of sensitive keys/tokens during import and export.
6. Round-trip fidelity: canonical Trace -> Langfuse Export -> Langfuse Import -> canonical Trace.
7. REST API v1 endpoints:
   - GET /api/v1/traces/{id}/langfuse
   - POST /api/v1/traces/langfuse/export
   - POST /api/v1/traces/langfuse/import
8. Typer CLI commands:
   - runport export-langfuse
   - runport import-langfuse
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
from runport.traces.langfuse import LangfuseExporter, LangfuseIngester
from runport.traces.repository import TraceRepository


@pytest.fixture
def test_db(tmp_path: Path, monkeypatch):
    """Sets up an isolated SQLite database for testing."""
    db_file = tmp_path / "langfuse_traces.db"
    monkeypatch.setattr(type(settings), "db_path", property(lambda self: db_file))
    db = DatabaseManager(db_file)
    db.init_db()

    # Create linked evaluation run for foreign key integrity
    t0 = datetime(2026, 11, 8, 10, 0, 0, tzinfo=timezone.utc)
    db.save_evaluation_run(
        {
            "run_id": "run-lf-01",
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


@pytest.fixture
def sample_trace() -> Trace:
    """Builds a rich sample canonical trace with hierarchy and mixed telemetry."""
    t0 = datetime(2026, 11, 8, 12, 0, 0, tzinfo=timezone.utc)
    t1 = t0 + timedelta(milliseconds=150)
    t2 = t0 + timedelta(milliseconds=850)
    t3 = t0 + timedelta(milliseconds=1200)

    trace = Trace(
        trace_id="tr-langfuse-001",
        run_id="run-lf-01",
        case_id="case-101",
        target_id="target-agent",
        session_id="session-user-77",
        name="SupportAgentWorkflow",
        status=SpanStatus.OK,
        start_time=t0,
        end_time=t3,
        attributes={
            "user_id": "usr-8899",
            "release": "v2.4.0",
            "environment": "staging",
            "tags": ["support", "agent"],
            "api_key": "sk-secret-1234567890abcdef123456",  # Sensitive key to scrub
        },
        spans=[
            # Root Agent span
            Span(
                trace_id="tr-langfuse-001",
                span_id="span-root-01",
                parent_span_id=None,
                name="TriageAgent",
                kind=SpanKind.AGENT,
                status=SpanStatus.OK,
                start_time=t0,
                end_time=t3,
                duration_ms=1200.0,
                attributes={"agent_type": "react"},
            ),
            # Child Tool span
            Span(
                trace_id="tr-langfuse-001",
                span_id="span-tool-01",
                parent_span_id="span-root-01",
                name="SearchKnowledgeBase",
                kind=SpanKind.TOOL,
                status=SpanStatus.OK,
                start_time=t0 + timedelta(milliseconds=50),
                end_time=t1,
                duration_ms=100.0,
                attributes={
                    "tool.name": "search_kb",
                    "input": {"query": "how to reset password"},
                    "output": {"articles": [101, 102]},
                },
                events=[
                    SpanEvent(
                        name="retrieval_cache_hit",
                        timestamp=t0 + timedelta(milliseconds=75),
                        attributes={"cache_key": "reset-pwd"},
                    )
                ],
            ),
            # Child LLM span with tokens & cost
            Span(
                trace_id="tr-langfuse-001",
                span_id="span-llm-01",
                parent_span_id="span-root-01",
                name="SummarizeAnswer",
                kind=SpanKind.LLM,
                status=SpanStatus.OK,
                start_time=t1,
                end_time=t2,
                duration_ms=700.0,
                provider="openrouter",
                model="gpt-4o-mini",
                prompt_tokens=150,
                completion_tokens=65,
                total_tokens=215,
                cost_usd="0.00034",
                cost_basis="ACTUAL",
                attributes={
                    "model_parameters": {"temperature": 0.2},
                    "bearer_token": "Bearer sensitive_token_xyz998877",  # Sensitive
                },
            ),
            # Unpriced span to test Invariant 1: 'Null is not 0'
            Span(
                trace_id="tr-langfuse-001",
                span_id="span-unpriced-01",
                parent_span_id="span-root-01",
                name="FormatOutput",
                kind=SpanKind.WORKFLOW_STEP,
                status=SpanStatus.OK,
                start_time=t2,
                end_time=t3,
                duration_ms=350.0,
                prompt_tokens=None,  # Missing tokens
                completion_tokens=None,
                total_tokens=None,
                cost_usd=None,  # Missing cost
                cost_basis=None,
            ),
        ],
    )
    return trace


def test_langfuse_export_batch(sample_trace: Trace):
    """Verifies canonical Trace correctly exports into Langfuse v2 batch ingestion payload."""
    payload = LangfuseExporter.export_trace(sample_trace)

    assert "batch" in payload
    events = payload["batch"]
    assert len(events) >= 5  # trace-create + 4 spans + 1 event

    # Check trace-create
    trace_events = [e for e in events if e["type"] == "trace-create"]
    assert len(trace_events) == 1
    t_body = trace_events[0]["body"]
    assert t_body["id"] == "tr-langfuse-001"
    assert t_body["name"] == "SupportAgentWorkflow"
    assert t_body["sessionId"] == "session-user-77"
    assert t_body["userId"] == "usr-8899"
    assert t_body["metadata"]["run_id"] == "run-lf-01"
    assert t_body["metadata"]["case_id"] == "case-101"

    # Invariant 7: Secret scrubbing
    assert "[REDACTED" in t_body["metadata"]["api_key"]
    assert "sk-secret" not in json.dumps(payload)

    # Check observations
    obs_events = [e for e in events if e["type"] == "observation-create"]
    obs_by_id = {o["body"]["id"]: o["body"] for o in obs_events}

    # Root span
    assert "span-root-01" in obs_by_id
    assert obs_by_id["span-root-01"]["type"] == "SPAN"
    assert obs_by_id["span-root-01"].get("parentObservationId") is None

    # LLM span
    assert "span-llm-01" in obs_by_id
    llm_obs = obs_by_id["span-llm-01"]
    assert llm_obs["type"] == "GENERATION"
    assert llm_obs["model"] == "gpt-4o-mini"
    assert llm_obs["parentObservationId"] == "span-root-01"
    assert llm_obs["usage"]["promptTokens"] == 150
    assert llm_obs["usage"]["completionTokens"] == 65
    assert llm_obs["usage"]["totalTokens"] == 215
    assert llm_obs["usage"]["totalCost"] == 0.00034
    assert "[REDACTED" in llm_obs["metadata"]["bearer_token"]

    # Invariant 1: 'Null is not 0'
    unpriced_obs = obs_by_id["span-unpriced-01"]
    # If unpriced, usage should either not be present or promptTokens not be 0
    if "usage" in unpriced_obs:
        assert "promptTokens" not in unpriced_obs["usage"] or unpriced_obs["usage"]["promptTokens"] is None
        assert "totalCost" not in unpriced_obs["usage"] or unpriced_obs["usage"]["totalCost"] is None


def test_langfuse_ingestion_and_roundtrip(test_db, sample_trace: Trace):
    """Verifies that an exported Langfuse batch can be cleanly ingested back into canonical storage."""
    repo = TraceRepository(db=test_db)

    # 1. Export
    batch_payload = LangfuseExporter.export_trace(sample_trace)

    # 2. Ingest
    ingested_traces = LangfuseIngester.ingest_to_repository(batch_payload, repo)
    assert len(ingested_traces) == 1
    t = ingested_traces[0]

    assert t.trace_id == "tr-langfuse-001"
    assert t.name == "SupportAgentWorkflow"
    assert t.session_id == "session-user-77"
    assert len(t.spans) == 4

    spans_by_id = {s.span_id: s for s in t.spans}
    assert "span-root-01" in spans_by_id
    assert "span-tool-01" in spans_by_id
    assert "span-llm-01" in spans_by_id
    assert "span-unpriced-01" in spans_by_id

    # Verify kinds
    assert spans_by_id["span-llm-01"].kind == SpanKind.LLM
    assert spans_by_id["span-tool-01"].kind == SpanKind.TOOL

    # Verify Invariant 1: Null is not 0
    assert spans_by_id["span-unpriced-01"].prompt_tokens is None
    assert spans_by_id["span-unpriced-01"].cost_usd is None

    # Verify Invariant 7: Zero secret leakage
    for s in t.spans:
        assert "sensitive" not in json.dumps(s.attributes)


def test_langfuse_ingestion_standalone_export(test_db):
    """Verifies ingestion of standard Langfuse hierarchical trace export format."""
    repo = TraceRepository(db=test_db)

    payload = {
        "id": "lf-ext-099",
        "name": "CustomerSupportFlow",
        "timestamp": "2026-11-08T14:00:00Z",
        "sessionId": "sess-99",
        "metadata": {
            "run_id": "run-lf-01",
            "environment": "production",
            "secret_key": "sk-sensitive-key-99999",
        },
        "observations": [
            {
                "id": "obs-root",
                "type": "SPAN",
                "name": "RootRouter",
                "startTime": "2026-11-08T14:00:00Z",
                "endTime": "2026-11-08T14:00:01Z",
                "level": "DEFAULT",
                "metadata": {"router_choice": "billing"},
            },
            {
                "id": "obs-llm",
                "traceId": "lf-ext-099",
                "parentObservationId": "obs-root",
                "type": "GENERATION",
                "name": "BillingResponseGen",
                "model": "claude-3-5-sonnet",
                "startTime": "2026-11-08T14:00:00.100Z",
                "endTime": "2026-11-08T14:00:00.900Z",
                "level": "DEFAULT",
                "usage": {
                    "promptTokens": 320,
                    "completionTokens": 140,
                    "totalTokens": 460,
                    "totalCost": 0.0028,
                },
                "metadata": {"temperature": 0.0},
            },
        ],
    }

    traces = LangfuseIngester.ingest_to_repository(payload, repo)
    assert len(traces) == 1
    tr = traces[0]
    assert tr.trace_id == "lf-ext-099"
    assert tr.name == "CustomerSupportFlow"
    assert len(tr.spans) == 2

    # Verify secret scrubbing
    assert "[REDACTED" in tr.attributes["secret_key"]
    assert "sk-sensitive" not in json.dumps(tr.attributes)

    # Verify database persistence
    persisted = repo.get_trace("lf-ext-099", include_spans=True)
    assert persisted is not None
    assert len(persisted.spans) == 2
    llm_span = [s for s in persisted.spans if s.kind == SpanKind.LLM][0]
    assert llm_span.prompt_tokens == 320
    assert llm_span.total_tokens == 460
    assert llm_span.cost_usd == "0.0028"


def test_langfuse_rest_api_v1(test_db, sample_trace: Trace):
    """Verifies REST API v1 endpoints for Langfuse export and ingestion."""
    repo = TraceRepository(db=test_db)
    repo.save_trace(sample_trace)

    app = create_app()
    client = TestClient(app)

    # 1. GET /api/v1/traces/{id}/langfuse
    resp = client.get(f"/api/v1/traces/{sample_trace.trace_id}/langfuse")
    assert resp.status_code == 200
    detail = resp.json()
    assert detail["id"] == sample_trace.trace_id
    assert "observations" in detail
    assert len(detail["observations"]) == 4

    # 2. POST /api/v1/traces/langfuse/export
    resp = client.post(
        "/api/v1/traces/langfuse/export",
        json={"trace_ids": [sample_trace.trace_id]},
    )
    assert resp.status_code == 200
    batch = resp.json()
    assert "batch" in batch
    assert len(batch["batch"]) >= 5

    # 3. POST /api/v1/traces/langfuse/import
    ingest_payload = {
        "batch": [
            {
                "type": "trace-create",
                "body": {
                    "id": "tr-api-import-001",
                    "name": "ApiIngestedTrace",
                    "metadata": {"run_id": "run-lf-01", "tag": "test"},
                },
            },
            {
                "type": "observation-create",
                "body": {
                    "id": "obs-api-001",
                    "traceId": "tr-api-import-001",
                    "type": "GENERATION",
                    "name": "ApiGen",
                    "usage": {"promptTokens": 50, "completionTokens": 20},
                },
            },
        ]
    }
    resp = client.post("/api/v1/traces/langfuse/import", json=ingest_payload)
    assert resp.status_code == 200
    res_data = resp.json()
    assert res_data["status"] == "ok"
    assert res_data["traces_ingested"] == 1
    assert "tr-api-import-001" in res_data["trace_ids"]

    # Verify saved in repository
    ingested_trace = repo.get_trace("tr-api-import-001", include_spans=True)
    assert ingested_trace is not None
    assert len(ingested_trace.spans) == 1
    assert ingested_trace.spans[0].prompt_tokens == 50


def test_langfuse_cli_commands(test_db, sample_trace: Trace, tmp_path: Path):
    """Verifies Typer CLI commands for export-langfuse and import-langfuse."""
    repo = TraceRepository(db=test_db)
    repo.save_trace(sample_trace)

    runner = CliRunner()
    export_file = tmp_path / "exported_langfuse.json"

    # Test export-langfuse
    res = runner.invoke(cli_app, ["export-langfuse", sample_trace.trace_id, "-o", str(export_file)])
    assert res.exit_code == 0
    assert export_file.exists()
    data = json.loads(export_file.read_text())
    assert "batch" in data

    # Test import-langfuse into new trace ID
    data["batch"][0]["body"]["id"] = "tr-cli-imported-002"
    for ev in data["batch"][1:]:
        if "traceId" in ev.get("body", {}):
            ev["body"]["traceId"] = "tr-cli-imported-002"

    import_file = tmp_path / "to_import_langfuse.json"
    import_file.write_text(json.dumps(data))

    res = runner.invoke(cli_app, ["import-langfuse", str(import_file)])
    assert res.exit_code == 0
    assert "Successfully ingested 1 trace" in res.stdout

    # Verify trace exists in DB
    imported_trace = repo.get_trace("tr-cli-imported-002", include_spans=True)
    assert imported_trace is not None
    assert len(imported_trace.spans) == 4

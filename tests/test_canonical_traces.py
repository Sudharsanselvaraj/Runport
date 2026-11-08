"""Tests for Milestone 2 - Phase 1: Canonical Trace & Span Data Models and SQLite Persistence.

Validates:
- Canonical Pydantic v2 models (Trace, Span, SpanKind, SpanStatus, SpanEvent).
- UTC timezone-aware datetime parsing and normalization.
- Invariant: 'Null is not 0' (distinguishing None from measured 0.0/0).
- Rejection of invalid negative telemetry (duration, tokens, cost).
- Prohibition of duration fabrication from missing timestamps.
- Hierarchy validation, cycle detection, and cross-trace isolation.
- Automatic secret scrubbing on errors, attributes, and events.
- SQLite persistence, retrieval, filtering by parent, run, and case.
- Foreign key enforcement, cascading deletes, and duplicate rejection.
- Atomic transaction rollbacks on batch insert failure.
- Status and completion updates without silent success falsification.
- Safe additive migration (v4) over existing database schemas with zero data loss.
- Multi-threaded concurrent writes under SQLite WAL mode.
- Backward compatibility with legacy trace models and schema re-exports.
"""

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
import sqlite3
import threading
import pytest
from pydantic import ValidationError

from runport.storage.db import DatabaseManager
from runport.traces.domain import (
    Span,
    SpanEvent,
    SpanKind,
    SpanStatus,
    Trace,
)
from runport.traces.repository import TraceRepository
from runport.traces.schema import (
    Span as SchemaSpan,
    Trace as SchemaTrace,
)


# =============================================================================
# 1. Canonical Model Construction & Serialization
# =============================================================================


def test_span_model_construction_and_serialization():
    t0 = datetime(2026, 11, 7, 12, 0, 0, tzinfo=timezone.utc)
    t1 = t0 + timedelta(milliseconds=150)

    event = SpanEvent(
        name="token_chunk",
        timestamp=t0 + timedelta(milliseconds=20),
        attributes={"chunk_size": 4},
    )

    span = Span(
        trace_id="tr-test-1",
        span_id="sp-llm-1",
        parent_span_id=None,
        name="call_llm",
        kind=SpanKind.LLM,
        status=SpanStatus.OK,
        start_time=t0,
        end_time=t1,
        duration_ms=150.0,
        provider="openrouter",
        model="anthropic/claude-3.5-sonnet",
        prompt_tokens=100,
        completion_tokens=50,
        total_tokens=150,
        cost_usd="0.000750",
        cost_basis="ESTIMATED",
        attributes={"temperature": 0.0},
        events=[event],
        attempt=1,
        source="native",
    )

    dumped = span.model_dump(mode="json")
    assert dumped["trace_id"] == "tr-test-1"
    assert dumped["span_id"] == "sp-llm-1"
    assert dumped["kind"] == "llm"
    assert dumped["status"] == "ok"
    assert dumped["duration_ms"] == 150.0
    assert dumped["prompt_tokens"] == 100
    assert dumped["completion_tokens"] == 50
    assert dumped["total_tokens"] == 150
    assert dumped["cost_usd"] == "0.000750"
    assert dumped["cost_basis"] == "ESTIMATED"
    assert len(dumped["events"]) == 1

    # Roundtrip from dumped JSON
    rebuilt = Span.model_validate(dumped)
    assert rebuilt.span_id == span.span_id
    assert rebuilt.start_time == span.start_time
    assert rebuilt.duration_ms == span.duration_ms


def test_enum_validation():
    # Valid span kinds
    for kind in ("llm", "tool", "retrieval", "workflow_step", "agent", "handoff", "rerank", "router", "other"):
        s = Span(trace_id="t1", span_id="s1", name="step", kind=SpanKind(kind))
        assert s.kind == kind

    # Invalid span kind rejected
    with pytest.raises(ValidationError):
        Span(trace_id="t1", span_id="s1", name="step", kind="invalid_kind")  # type: ignore

    # Valid span status
    for status in ("ok", "error", "timeout", "cancelled", "unset"):
        s = Span(trace_id="t1", span_id="s1", name="step", kind=SpanKind.LLM, status=SpanStatus(status))
        assert s.status == status

    # Invalid status rejected
    with pytest.raises(ValidationError):
        Span(trace_id="t1", span_id="s1", name="step", kind=SpanKind.LLM, status="unknown_status")  # type: ignore


# =============================================================================
# 2. Invariant: Null is not 0 (Distinguishing None from 0)
# =============================================================================


def test_null_vs_zero_telemetry_semantics():
    # Case A: Missing telemetry remains None
    span_unmeasured = Span(
        trace_id="t1",
        span_id="s1",
        name="unmeasured",
        kind=SpanKind.TOOL,
        prompt_tokens=None,
        completion_tokens=None,
        total_tokens=None,
        duration_ms=None,
        cost_usd=None,
        cost_basis=None,
    )
    assert span_unmeasured.prompt_tokens is None
    assert span_unmeasured.completion_tokens is None
    assert span_unmeasured.total_tokens is None
    assert span_unmeasured.duration_ms is None
    assert span_unmeasured.cost_usd is None
    assert span_unmeasured.cost_basis is None

    # Case B: Measured zero remains explicitly zero and is not confused with None
    span_zero = Span(
        trace_id="t1",
        span_id="s2",
        name="measured_zero",
        kind=SpanKind.LLM,
        prompt_tokens=0,
        completion_tokens=0,
        total_tokens=0,
        duration_ms=0.0,
        cost_usd="0.000000",
        cost_basis="UNAVAILABLE",
    )
    assert span_zero.prompt_tokens is not None and span_zero.prompt_tokens == 0
    assert span_zero.completion_tokens is not None and span_zero.completion_tokens == 0
    assert span_zero.total_tokens is not None and span_zero.total_tokens == 0
    assert span_zero.duration_ms is not None and span_zero.duration_ms == 0.0
    assert span_zero.cost_usd is not None and span_zero.cost_usd == "0.000000"
    assert span_zero.cost_basis == "UNAVAILABLE"


# =============================================================================
# 3. Telemetry Validation: Rejection of Invalid Negative Values
# =============================================================================


def test_invalid_negative_telemetry_rejection():
    # Negative duration
    with pytest.raises(ValidationError, match="duration_ms must be non-negative"):
        Span(trace_id="t1", span_id="s1", name="test", kind=SpanKind.LLM, duration_ms=-1.5)

    # Negative prompt tokens
    with pytest.raises(ValidationError, match="Token counts must be non-negative"):
        Span(trace_id="t1", span_id="s1", name="test", kind=SpanKind.LLM, prompt_tokens=-10)

    # Negative completion tokens
    with pytest.raises(ValidationError, match="Token counts must be non-negative"):
        Span(trace_id="t1", span_id="s1", name="test", kind=SpanKind.LLM, completion_tokens=-1)

    # Boolean passed for tokens must be rejected
    with pytest.raises(ValidationError, match="Token counts cannot be boolean"):
        Span(trace_id="t1", span_id="s1", name="test", kind=SpanKind.LLM, prompt_tokens=True)  # type: ignore

    # Negative cost
    with pytest.raises(ValidationError, match="cost_usd must be non-negative"):
        Span(trace_id="t1", span_id="s1", name="test", kind=SpanKind.LLM, cost_usd="-0.01")

    # Non-numeric cost string
    with pytest.raises(ValidationError, match="Invalid decimal string"):
        Span(trace_id="t1", span_id="s1", name="test", kind=SpanKind.LLM, cost_usd="not_a_dollar_amount")

    # Attempt < 1
    with pytest.raises(ValidationError):
        Span(trace_id="t1", span_id="s1", name="test", kind=SpanKind.LLM, attempt=0)


# =============================================================================
# 4. UTC Timestamps & No Duration Fabrication
# =============================================================================


def test_utc_timestamp_normalization():
    # Naive datetime is automatically converted to timezone.utc
    naive_dt = datetime(2026, 11, 7, 10, 0, 0)
    span = Span(trace_id="t1", span_id="s1", name="test", kind=SpanKind.TOOL, start_time=naive_dt)
    assert span.start_time is not None
    assert span.start_time.tzinfo == timezone.utc

    # ISO string with Z
    span2 = Span(trace_id="t1", span_id="s2", name="test", kind=SpanKind.TOOL, start_time="2026-11-07T10:00:00Z")  # type: ignore
    assert span2.start_time is not None
    assert span2.start_time.tzinfo == timezone.utc

    # Inverted timestamps (end_time < start_time) rejected
    t0 = datetime(2026, 11, 7, 12, 0, 0, tzinfo=timezone.utc)
    t_past = t0 - timedelta(seconds=5)
    with pytest.raises(ValidationError, match="end_time .* cannot be earlier than start_time"):
        Span(trace_id="t1", span_id="s1", name="test", kind=SpanKind.TOOL, start_time=t0, end_time=t_past)


def test_no_duration_fabrication_from_missing_timestamps():
    t0 = datetime(2026, 11, 7, 12, 0, 0, tzinfo=timezone.utc)

    # Only start_time provided: duration_ms MUST NOT be fabricated
    span1 = Span(trace_id="t1", span_id="s1", name="test", kind=SpanKind.AGENT, start_time=t0)
    assert span1.duration_ms is None

    # Only end_time provided: duration_ms MUST NOT be fabricated
    span2 = Span(trace_id="t1", span_id="s2", name="test", kind=SpanKind.AGENT, end_time=t0)
    assert span2.duration_ms is None

    # Neither provided: duration_ms remains None
    span3 = Span(trace_id="t1", span_id="s3", name="test", kind=SpanKind.AGENT)
    assert span3.duration_ms is None

    # Both provided without explicit duration: computes legitimate delta
    t1 = t0 + timedelta(milliseconds=250)
    span4 = Span(trace_id="t1", span_id="s4", name="test", kind=SpanKind.AGENT, start_time=t0, end_time=t1)
    assert span4.duration_ms == 250.0

    # Both provided WITH explicit measured duration: explicit duration is preserved
    span5 = Span(
        trace_id="t1",
        span_id="s5",
        name="test",
        kind=SpanKind.AGENT,
        start_time=t0,
        end_time=t1,
        duration_ms=248.5,
    )
    assert span5.duration_ms == 248.5


# =============================================================================
# 5. Secret Scrubbing & Redaction
# =============================================================================


def test_secret_scrubbing_on_span_and_trace():
    sensitive_auth = "Bearer sk-or-v1-abcdef1234567890abcdef123456"
    sensitive_api_key = "sk-1234567890abcdef1234567890"

    # Span error scrubbing
    span = Span(
        trace_id="t1",
        span_id="s1",
        name="call_api",
        kind=SpanKind.LLM,
        error=f"Request failed with {sensitive_auth} using key {sensitive_api_key}",
        attributes={
            "authorization": sensitive_auth,
            "nested": {"token": "secret_token_123456789"},
        },
    )
    assert "[REDACTED_SECRET]" in (span.error or "")
    assert "[REDACTED_API_KEY]" in (span.error or "")
    assert sensitive_api_key not in (span.error or "")
    assert span.attributes["authorization"] == "[REDACTED_SECRET]"
    assert span.attributes["nested"]["token"] == "[REDACTED_SECRET]"

    # Event attributes scrubbing
    ev = SpanEvent(
        name="log",
        timestamp=datetime.now(timezone.utc),
        attributes={"secret_key": "my_hidden_pass_123"},
    )
    assert ev.attributes["secret_key"] == "[REDACTED_SECRET]"

    # Trace attributes scrubbing
    trace = Trace(
        trace_id="t1",
        name="workflow",
        attributes={"api_key": sensitive_api_key},
    )
    assert trace.attributes["api_key"] == "[REDACTED_SECRET]"


# =============================================================================
# 6. Hierarchy Validation, Cross-Trace Isolation & Cycle Detection
# =============================================================================


def test_parent_child_hierarchy_and_cross_trace_isolation():
    # Self-referential parent rejected
    with pytest.raises(ValidationError, match="parent_span_id cannot be identical to span_id"):
        Span(trace_id="t1", span_id="s1", parent_span_id="s1", name="step", kind=SpanKind.TOOL)

    # Valid tree
    root = Span(trace_id="tr-1", span_id="root", name="root", kind=SpanKind.WORKFLOW_STEP)
    child = Span(trace_id="tr-1", span_id="child", parent_span_id="root", name="child", kind=SpanKind.LLM)
    grandchild = Span(
        trace_id="tr-1",
        span_id="grandchild",
        parent_span_id="child",
        name="grandchild",
        kind=SpanKind.TOOL,
    )

    trace = Trace(trace_id="tr-1", name="pipeline", spans=[root, child, grandchild])
    assert len(trace.get_root_spans()) == 1
    assert trace.get_root_spans()[0].span_id == "root"
    assert len(trace.get_child_spans("root")) == 1
    assert trace.get_child_spans("root")[0].span_id == "child"
    assert len(trace.get_child_spans("child")) == 1
    assert trace.get_child_spans("child")[0].span_id == "grandchild"

    # Cross-trace span inclusion rejected
    foreign_span = Span(trace_id="tr-OTHER", span_id="foreign", name="foreign", kind=SpanKind.TOOL)
    with pytest.raises(ValueError, match="Cross-trace span rejected"):
        Trace(trace_id="tr-1", name="pipeline", spans=[root, foreign_span])

    # Unknown parent referenced within trace rejected
    orphan_child = Span(
        trace_id="tr-1",
        span_id="orphan",
        parent_span_id="nonexistent-parent",
        name="orphan",
        kind=SpanKind.TOOL,
    )
    with pytest.raises(ValueError, match="references unknown parent"):
        Trace(trace_id="tr-1", name="pipeline", spans=[orphan_child])

    # Duplicate span ID rejected
    dup_span = Span(trace_id="tr-1", span_id="root", name="duplicate", kind=SpanKind.TOOL)
    with pytest.raises(ValueError, match="Duplicate span_id"):
        Trace(trace_id="tr-1", name="pipeline", spans=[root, dup_span])

    # Cycle detection: A -> B -> A
    cycle_a = Span(trace_id="tr-1", span_id="cycle_a", parent_span_id="cycle_b", name="a", kind=SpanKind.TOOL)
    cycle_b = Span(trace_id="tr-1", span_id="cycle_b", parent_span_id="cycle_a", name="b", kind=SpanKind.TOOL)
    with pytest.raises(ValueError, match="Cyclic parent-child span relationship"):
        Trace(trace_id="tr-1", name="pipeline", spans=[cycle_a, cycle_b])


# =============================================================================
# 7. SQLite Persistence, Retrieval & Filtering
# =============================================================================


def test_trace_and_span_persistence_lifecycle(tmp_path: Path):
    db = DatabaseManager(tmp_path / "traces.db")
    db.init_db()
    repo = TraceRepository(db)

    # 1. Create a linked evaluation run for foreign key validity
    t0 = datetime(2026, 11, 7, 10, 0, 0, tzinfo=timezone.utc)
    db.save_evaluation_run(
        {
            "run_id": "run-m2",
            "timestamp": t0.isoformat(),
            "model_id": "anthropic/claude-3.5-sonnet",
            "dataset_path": "benchmark.jsonl",
            "total_cases": 1,
            "completed_cases": 1,
            "failed_cases": 0,
            "total_cost_usd": "0.001000",
        }
    )

    # 2. Persist Trace
    trace = Trace(
        trace_id="tr-100",
        run_id="run-m2",
        case_id="case-42",
        target_id="target-dify-1",
        name="rag_evaluation_case_42",
        status=SpanStatus.OK,
        start_time=t0,
        end_time=t0 + timedelta(milliseconds=450),
        attributes={"dataset": "financial_qa", "auth": "Bearer secret_test_token_123"},
    )
    repo.create_trace(trace)

    # 3. Create Spans
    root_span = Span(
        trace_id="tr-100",
        span_id="sp-root",
        name="workflow_orchestrator",
        kind=SpanKind.WORKFLOW_STEP,
        status=SpanStatus.OK,
        start_time=t0,
        end_time=t0 + timedelta(milliseconds=450),
        duration_ms=450.0,
    )
    retrieval_span = Span(
        trace_id="tr-100",
        span_id="sp-retrieval",
        parent_span_id="sp-root",
        name="vector_search",
        kind=SpanKind.RETRIEVAL,
        status=SpanStatus.OK,
        start_time=t0 + timedelta(milliseconds=10),
        end_time=t0 + timedelta(milliseconds=80),
        duration_ms=70.0,
        attributes={"top_k": 3},
    )
    llm_span = Span(
        trace_id="tr-100",
        span_id="sp-llm",
        parent_span_id="sp-root",
        name="answer_generation",
        kind=SpanKind.LLM,
        status=SpanStatus.OK,
        start_time=t0 + timedelta(milliseconds=90),
        end_time=t0 + timedelta(milliseconds=440),
        duration_ms=350.0,
        prompt_tokens=500,
        completion_tokens=150,
        total_tokens=650,
        cost_usd="0.000975",
        cost_basis="ACTUAL",
    )

    repo.create_spans([root_span, retrieval_span, llm_span])

    # 4. Retrieve Trace with Spans
    loaded_trace = repo.get_trace("tr-100", include_spans=True)
    assert loaded_trace is not None
    assert loaded_trace.trace_id == "tr-100"
    assert loaded_trace.run_id == "run-m2"
    assert loaded_trace.case_id == "case-42"
    assert loaded_trace.status == SpanStatus.OK
    assert loaded_trace.attributes["auth"] == "[REDACTED_SECRET]"
    assert len(loaded_trace.spans) == 3

    # Check hierarchy navigation
    assert len(loaded_trace.get_root_spans()) == 1
    assert loaded_trace.get_root_spans()[0].span_id == "sp-root"
    children = loaded_trace.get_child_spans("sp-root")
    assert len(children) == 2
    child_ids = {c.span_id for c in children}
    assert child_ids == {"sp-retrieval", "sp-llm"}

    # Check span telemetry accuracy ('Null is not 0' preserved)
    ret_loaded = loaded_trace.get_span("sp-retrieval")
    assert ret_loaded is not None
    assert ret_loaded.prompt_tokens is None  # Not reported
    assert ret_loaded.cost_usd is None

    llm_loaded = loaded_trace.get_span("sp-llm")
    assert llm_loaded is not None
    assert llm_loaded.prompt_tokens == 500
    assert llm_loaded.completion_tokens == 150
    assert llm_loaded.total_tokens == 650
    assert llm_loaded.cost_usd == "0.000975"
    assert llm_loaded.cost_basis == "ACTUAL"

    # 5. Filter by parent
    root_only = repo.get_spans_by_parent("tr-100", None)
    assert len(root_only) == 1
    assert root_only[0].span_id == "sp-root"

    children_only = repo.get_spans_by_parent("tr-100", "sp-root")
    assert len(children_only) == 2

    # 6. Query by run and case
    run_traces = repo.get_traces_for_run("run-m2", include_spans=True)
    assert len(run_traces) == 1
    assert run_traces[0].trace_id == "tr-100"

    case_traces = repo.get_traces_for_case("run-m2", "case-42", include_spans=True)
    assert len(case_traces) == 1
    assert case_traces[0].trace_id == "tr-100"


# =============================================================================
# 8. Uniqueness, Foreign Keys & Cascading Deletion
# =============================================================================


def test_trace_and_span_constraints_and_cascade(tmp_path: Path):
    db = DatabaseManager(tmp_path / "constraints.db")
    db.init_db()
    repo = TraceRepository(db)

    # Duplicate trace ID rejected
    t1 = Trace(trace_id="tr-uniq", name="trace_1")
    repo.create_trace(t1)
    with pytest.raises(sqlite3.IntegrityError):
        repo.create_trace(t1)

    # Duplicate (trace_id, span_id) rejected
    s1 = Span(trace_id="tr-uniq", span_id="sp-1", name="step 1", kind=SpanKind.TOOL)
    repo.create_span(s1)
    with pytest.raises(sqlite3.IntegrityError):
        repo.create_span(s1)

    # Orphan span referencing non-existent trace rejected by FK
    orphan = Span(trace_id="tr-NONEXISTENT", span_id="sp-orphan", name="orphan", kind=SpanKind.LLM)
    with pytest.raises(sqlite3.IntegrityError):
        repo.create_span(orphan)

    # Cascading delete: deleting trace automatically deletes its spans
    with db.get_connection() as conn:
        conn.execute("DELETE FROM traces WHERE trace_id = 'tr-uniq'")
        conn.commit()

    assert repo.get_trace("tr-uniq") is None
    assert len(repo.get_spans("tr-uniq")) == 0


def test_atomic_transaction_rollback(tmp_path: Path):
    db = DatabaseManager(tmp_path / "rollback.db")
    db.init_db()
    repo = TraceRepository(db)

    repo.create_trace(Trace(trace_id="tr-tx", name="tx_test"))

    s1 = Span(trace_id="tr-tx", span_id="sp-1", name="step 1", kind=SpanKind.TOOL)
    s2_dup = Span(trace_id="tr-tx", span_id="sp-1", name="step 2 duplicate", kind=SpanKind.LLM)

    # Batch insert with duplicate should raise and rollback completely
    with pytest.raises(sqlite3.IntegrityError):
        repo.create_spans([s1, s2_dup])

    # Verify that sp-1 was NOT saved
    spans = repo.get_spans("tr-tx")
    assert len(spans) == 0


# =============================================================================
# 9. Status and Completion Updates Without Falsification
# =============================================================================


def test_status_updates_and_error_handling(tmp_path: Path):
    db = DatabaseManager(tmp_path / "status.db")
    db.init_db()
    repo = TraceRepository(db)

    t0 = datetime(2026, 11, 7, 10, 0, 0, tzinfo=timezone.utc)
    trace = Trace(trace_id="tr-update", name="in_progress_trace", status=SpanStatus.UNSET, start_time=t0)
    repo.create_trace(trace)

    span = Span(
        trace_id="tr-update",
        span_id="sp-update",
        name="executing_step",
        kind=SpanKind.TOOL,
        status=SpanStatus.UNSET,
        start_time=t0,
    )
    repo.create_span(span)

    # Update span to failed status with sanitized error
    t_end = t0 + timedelta(milliseconds=85)
    repo.update_span_status(
        trace_id="tr-update",
        span_id="sp-update",
        status=SpanStatus.ERROR,
        end_time=t_end,
        error="Connection reset by peer; token Bearer secret_live_key_987654321",
    )

    updated_span = repo.get_spans("tr-update")[0]
    assert updated_span.status == SpanStatus.ERROR
    assert updated_span.duration_ms == 85.0
    assert "[REDACTED_SECRET]" in (updated_span.error or "")
    assert "secret_live_key_987654321" not in (updated_span.error or "")

    # Update trace status to ERROR
    repo.update_trace_status("tr-update", status=SpanStatus.ERROR, end_time=t_end)
    updated_trace = repo.get_trace("tr-update", include_spans=False)
    assert updated_trace is not None
    assert updated_trace.status == SpanStatus.ERROR
    assert updated_trace.end_time == t_end

    # Nonexistent IDs raise KeyError
    with pytest.raises(KeyError):
        repo.update_trace_status("nonexistent-trace", status=SpanStatus.OK)

    with pytest.raises(KeyError):
        repo.update_span_status("tr-update", "nonexistent-span", status=SpanStatus.OK)


# =============================================================================
# 10. Database Migration Over Existing Data (Safe Migration v4)
# =============================================================================


def test_migration_v4_preserves_existing_database(tmp_path: Path):
    legacy_db_file = tmp_path / "legacy_v3.db"

    # Simulate an existing database at migration v3
    conn = sqlite3.connect(str(legacy_db_file))
    conn.execute("""
        CREATE TABLE schema_migrations (
            version INTEGER PRIMARY KEY,
            applied_at TEXT NOT NULL,
            description TEXT NOT NULL
        )
    """)
    conn.execute("INSERT INTO schema_migrations VALUES (1, '2026-01-01', 'v1')")
    conn.execute("INSERT INTO schema_migrations VALUES (2, '2026-01-01', 'v2')")
    conn.execute("INSERT INTO schema_migrations VALUES (3, '2026-01-01', 'v3')")
    conn.execute("""
        CREATE TABLE evaluation_runs (
            run_id TEXT PRIMARY KEY,
            timestamp TEXT NOT NULL,
            model_id TEXT NOT NULL,
            dataset_path TEXT NOT NULL,
            total_cases INTEGER NOT NULL,
            completed_cases INTEGER NOT NULL,
            failed_cases INTEGER NOT NULL,
            total_cost_usd TEXT NOT NULL,
            mean_latency_ms REAL,
            mean_accuracy REAL,
            mean_groundedness REAL,
            mean_overall_score REAL,
            is_dry_run INTEGER NOT NULL DEFAULT 1,
            notes TEXT
        )
    """)
    conn.execute("""
        INSERT INTO evaluation_runs VALUES (
            'legacy-run-1', '2026-01-01T00:00:00Z', 'claude-3-haiku', 'data.jsonl',
            10, 10, 0, '0.0150', 80.0, 0.95, 0.90, 0.92, 0, 'existing benchmark run'
        )
    """)
    conn.commit()
    conn.close()

    # Now run DatabaseManager.init_db()
    mgr = DatabaseManager(legacy_db_file)
    mgr.init_db()

    # Verify that existing run row remains completely intact
    existing_run = mgr.get_evaluation_run("legacy-run-1")
    assert existing_run is not None
    assert existing_run["notes"] == "existing benchmark run"
    assert existing_run["mean_accuracy"] == 0.95

    # Verify that traces and spans tables and indexes now exist
    with mgr.get_connection() as c:
        tables = {r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
        assert "traces" in tables
        assert "spans" in tables

        # Verify migrations were recorded (including v4 traces and v5 api_keys/run_jobs)
        versions = [r[0] for r in c.execute("SELECT version FROM schema_migrations ORDER BY version").fetchall()]
        assert versions == [1, 2, 3, 4, 5]


# =============================================================================
# 11. Concurrent Writes Under SQLite WAL Mode
# =============================================================================


def test_concurrent_writes_under_wal(tmp_path: Path):
    db_file = tmp_path / "concurrent_wal.db"
    db = DatabaseManager(db_file)
    db.init_db()

    num_threads = 4
    traces_per_thread = 5

    def worker(worker_id: int):
        w_db = DatabaseManager(db_file)
        w_repo = TraceRepository(w_db)
        for i in range(traces_per_thread):
            t_id = f"tr-w{worker_id}-{i}"
            trace = Trace(trace_id=t_id, name=f"trace_w{worker_id}_{i}")
            w_repo.create_trace(trace)
            span = Span(
                trace_id=t_id,
                span_id=f"sp-w{worker_id}-{i}",
                name="step",
                kind=SpanKind.TOOL,
            )
            w_repo.create_span(span)

    threads = [threading.Thread(target=worker, args=(tid,)) for tid in range(num_threads)]
    for th in threads:
        th.start()
    for th in threads:
        th.join()

    # Verify all traces were safely persisted
    repo = TraceRepository(db)
    for wid in range(num_threads):
        for i in range(traces_per_thread):
            loaded = repo.get_trace(f"tr-w{wid}-{i}", include_spans=True)
            assert loaded is not None
            assert len(loaded.spans) == 1


# =============================================================================
# 12. Schema Compatibility Re-exports
# =============================================================================


def test_schema_reexport_compatibility():
    assert SchemaTrace is Trace
    assert SchemaSpan is Span

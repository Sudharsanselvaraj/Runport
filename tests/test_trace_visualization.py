"""Unit tests for Milestone 2 - Phase 4: Trace Visualization.

Tests:
1. Terminal UI trace rendering (Tree, Panel, Table).
2. FastAPI REST endpoints for traces (/api/traces, /api/traces/{trace_id}, /api/runs/{run_id}/traces).
3. CLI commands (`runport traces`, `runport trace <trace_id>`).
"""

from datetime import datetime, timezone, timedelta
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from rich.tree import Tree
from rich.panel import Panel
from rich.table import Table
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
from runport.traces.repository import TraceRepository
from runport.tui.traces_view import (
    render_trace_tree,
    render_trace_panel,
    render_traces_table,
)


@pytest.fixture
def test_db(tmp_path: Path, monkeypatch):
    """Sets up an isolated SQLite database for testing."""
    db_file = tmp_path / "vis_traces.db"
    monkeypatch.setattr(type(settings), "db_path", property(lambda self: db_file))
    db = DatabaseManager(db_file)
    db.init_db()

    # Create linked evaluation run for foreign key integrity
    t0 = datetime(2026, 11, 7, 10, 0, 0, tzinfo=timezone.utc)
    db.save_evaluation_run(
        {
            "run_id": "run-vis-100",
            "timestamp": t0.isoformat(),
            "model_id": "anthropic/claude-3.5-sonnet",
            "dataset_path": "benchmark.jsonl",
            "total_cases": 1,
            "completed_cases": 1,
            "failed_cases": 0,
            "duration_ms": 450.0,
            "total_cost_usd": "0.000045",
        }
    )
    return db


@pytest.fixture
def sample_trace() -> Trace:
    """Creates a sample canonical trace with parent-child span hierarchy."""
    t0 = datetime(2026, 11, 7, 12, 0, 0, tzinfo=timezone.utc)
    t1 = t0 + timedelta(milliseconds=450)
    t_llm_start = t0 + timedelta(milliseconds=50)
    t_llm_end = t0 + timedelta(milliseconds=250)
    t_tool_start = t0 + timedelta(milliseconds=260)
    t_tool_end = t0 + timedelta(milliseconds=420)

    root_span = Span(
        trace_id="tr-vis-1",
        span_id="sp-root",
        parent_span_id=None,
        name="agent_workflow",
        kind=SpanKind.AGENT,
        status=SpanStatus.OK,
        start_time=t0,
        end_time=t1,
        duration_ms=450.0,
        attributes={"agent_type": "react"},
    )
    llm_span = Span(
        trace_id="tr-vis-1",
        span_id="sp-llm",
        parent_span_id="sp-root",
        name="generate_reasoning",
        kind=SpanKind.LLM,
        status=SpanStatus.OK,
        start_time=t_llm_start,
        end_time=t_llm_end,
        duration_ms=200.0,
        model="gpt-4o-mini",
        prompt_tokens=120,
        completion_tokens=45,
        total_tokens=165,
        cost_usd="0.000045",
        cost_basis="ESTIMATED",
    )
    tool_span = Span(
        trace_id="tr-vis-1",
        span_id="sp-tool",
        parent_span_id="sp-root",
        name="web_search",
        kind=SpanKind.TOOL,
        status=SpanStatus.OK,
        start_time=t_tool_start,
        end_time=t_tool_end,
        duration_ms=160.0,
        attributes={"query": "python 3.11 release"},
        events=[
            SpanEvent(
                name="tool_call_started",
                timestamp=t_tool_start,
                attributes={"tool": "search"},
            )
        ],
    )

    return Trace(
        trace_id="tr-vis-1",
        run_id="run-vis-100",
        case_id="case-42",
        target_id="support-agent",
        name="case-42-execution",
        status=SpanStatus.OK,
        start_time=t0,
        end_time=t1,
        spans=[root_span, llm_span, tool_span],
    )


# =============================================================================
# 1. Terminal UI Visualization Tests
# =============================================================================


def test_render_trace_tree(sample_trace: Trace):
    tree = render_trace_tree(sample_trace)
    assert isinstance(tree, Tree)
    assert len(tree.children) == 1  # Root span
    root_node = tree.children[0]
    assert len(root_node.children) == 2  # LLM and Tool children


def test_render_trace_tree_with_highlight(sample_trace: Trace):
    tree = render_trace_tree(sample_trace, highlight_span_id="sp-llm")
    assert isinstance(tree, Tree)


def test_render_trace_panel(sample_trace: Trace):
    panel = render_trace_panel(sample_trace)
    assert isinstance(panel, Panel)


def test_render_traces_table(sample_trace: Trace):
    table = render_traces_table([sample_trace])
    assert isinstance(table, Table)
    assert table.row_count == 1


# =============================================================================
# 2. REST API Endpoints Tests
# =============================================================================


def test_api_list_traces(test_db: DatabaseManager, sample_trace: Trace):
    repo = TraceRepository(test_db)
    repo.save_trace(sample_trace)

    app = create_app()
    client = TestClient(app)

    # 1. List all traces
    res = client.get("/api/traces")
    assert res.status_code == 200
    data = res.json()
    assert len(data) == 1
    assert data[0]["trace_id"] == "tr-vis-1"
    assert data[0]["run_id"] == "run-vis-100"

    # 2. Filter by run_id
    res_run = client.get("/api/traces?run_id=run-vis-100")
    assert res_run.status_code == 200
    assert len(res_run.json()) == 1

    # 3. Filter by non-existent run_id
    res_empty = client.get("/api/traces?run_id=non-existent-run")
    assert res_empty.status_code == 200
    assert len(res_empty.json()) == 0


def test_api_trace_detail_and_404(test_db: DatabaseManager, sample_trace: Trace):
    repo = TraceRepository(test_db)
    repo.save_trace(sample_trace)

    app = create_app()
    client = TestClient(app)

    # Found
    res = client.get("/api/traces/tr-vis-1")
    assert res.status_code == 200
    data = res.json()
    assert data["trace_id"] == "tr-vis-1"
    assert len(data["spans"]) == 3

    # Not found
    res_404 = client.get("/api/traces/missing-trace-id")
    assert res_404.status_code == 404
    assert "not found" in res_404.json()["detail"].lower()


def test_api_run_traces(test_db: DatabaseManager, sample_trace: Trace):
    repo = TraceRepository(test_db)
    repo.save_trace(sample_trace)

    app = create_app()
    client = TestClient(app)

    res = client.get("/api/runs/run-vis-100/traces")
    assert res.status_code == 200
    data = res.json()
    assert len(data) == 1
    assert data[0]["trace_id"] == "tr-vis-1"


# =============================================================================
# 3. CLI Commands Tests
# =============================================================================


def test_cli_traces_list_command(test_db: DatabaseManager, sample_trace: Trace):
    repo = TraceRepository(test_db)
    repo.save_trace(sample_trace)

    runner = CliRunner()
    result = runner.invoke(cli_app, ["traces"])
    assert result.exit_code == 0
    assert "tr-vis-1" in result.stdout or "run-vis-100" in result.stdout


def test_cli_trace_detail_command(test_db: DatabaseManager, sample_trace: Trace):
    repo = TraceRepository(test_db)
    repo.save_trace(sample_trace)

    runner = CliRunner()
    result = runner.invoke(cli_app, ["trace", "tr-vis-1"])
    assert result.exit_code == 0
    assert "tr-vis-1" in result.stdout
    assert "agent_workflow" in result.stdout


def test_cli_trace_not_found(test_db: DatabaseManager):
    runner = CliRunner()
    result = runner.invoke(cli_app, ["trace", "non-existent-trace"])
    assert result.exit_code != 0 or "not found" in result.stdout.lower()

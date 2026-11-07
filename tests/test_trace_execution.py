"""Unit and integration tests for Milestone 2 - Phase 2: Runtime Trace & Trajectory Instrumentation.

Validates:
- GenericRunner automatically instruments and persists a canonical Trace and root Span per executed case.
- 'Null is not 0' invariant: missing tokens, cost, and latency remain None, while measured 0 is preserved.
- Automatic trajectory stitching: target child spans are bound to the trace and root span.
- Multi-level nested trajectory hierarchies (root -> step -> tool).
- Connector trajectory emissions:
  * McpToolTarget emits SpanKind.TOOL spans with latency, arguments, and status.
  * DifyConnector emits SpanKind.WORKFLOW_STEP / LLM / RETRIEVAL spans from node execution events.
  * RagPipelineTarget emits decoupled RETRIEVAL and LLM spans.
- Automatic secret scrubbing on trace and span attributes, errors, and metadata.
- Error and timeout case status mapping (ERROR, TIMEOUT).
- Partial run execution under budget halt preserves already executed traces in SQLite.
- Complete offline test execution with blocked sockets.
"""

from datetime import datetime, timezone
from decimal import Decimal
import json
from pathlib import Path
import tempfile
from typing import Any, Dict, List, Optional
import pytest

from live_fakes import LiveFakeProvider
from runport.connectors.dify import DifyConnector, _build_dify_node_spans
from runport.connectors.mcp import McpToolTarget
from runport.connectors.python_target import PythonCallableTarget
from runport.core.approvers import TokenApprover
from runport.core.budget import BudgetService
from runport.core.workspace import BudgetConfig, WorkspaceConfig
from runport.rag.target import RagPipelineTarget
from runport.rag.models import RetrievalResult
from runport.rag.retriever import BaseRetriever
from runport.runs.executor import GenericRunner
from runport.runs.planner import create_execution_plan
from runport.storage.db import DatabaseManager
from runport.targets.base import (
    BillingMode,
    CostBasis,
    Target,
    TargetPricing,
    TargetResult,
    TargetStatus,
    TargetType,
)
from runport.traces.domain import Span, SpanKind, SpanStatus, Trace
from runport.traces.repository import TraceRepository


# =============================================================================
# Helper Fixtures and Test Targets
# =============================================================================


class MockTelemetryTarget(Target):
    """Target allowing precise control over returned telemetry for invariant testing."""

    def __init__(
        self,
        target_id: str = "mock-telemetry",
        status: TargetStatus = TargetStatus.SUCCESS,
        latency_ms: Optional[float] = None,
        tokens_in: Optional[int] = None,
        tokens_out: Optional[int] = None,
        cost_usd: Optional[Decimal] = None,
        cost_basis: CostBasis = CostBasis.UNAVAILABLE,
        trajectory: Optional[List[Span]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        error_message: Optional[str] = None,
    ):
        super().__init__(target_id=target_id, name="Mock Telemetry Target", target_type=TargetType.RAW_MODEL)
        self.ret_status = status
        self.ret_latency = latency_ms
        self.ret_tokens_in = tokens_in
        self.ret_tokens_out = tokens_out
        self.ret_cost_usd = cost_usd
        self.ret_cost_basis = cost_basis
        self.ret_trajectory = trajectory
        self.ret_metadata = metadata or {}
        self.ret_error = error_message

    def execute(self, payload: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> TargetResult:
        return TargetResult(
            target_id=self.target_id,
            status=self.ret_status,
            output_text="Executed output" if self.ret_status == TargetStatus.SUCCESS else None,
            latency_ms=self.ret_latency,
            tokens_in=self.ret_tokens_in,
            tokens_out=self.ret_tokens_out,
            cost_usd=self.ret_cost_usd,
            cost_basis=self.ret_cost_basis,
            trajectory=self.ret_trajectory,
            metadata=self.ret_metadata,
            error_message=self.ret_error,
        )


@pytest.fixture
def temp_db(tmp_path: Path) -> DatabaseManager:
    db = DatabaseManager(db_path=tmp_path / "test_traces.db")
    db.init_db()
    return db


# =============================================================================
# 1. Canonical Trace & Span Creation per Case
# =============================================================================


def test_generic_runner_persists_canonical_trace_per_case(tmp_path: Path, temp_db: DatabaseManager):
    """GenericRunner persists a canonical Trace and root Span for each evaluated case."""
    ds_file = tmp_path / "ds.jsonl"
    ds_file.write_text('{"id": "case-1", "classification": "SYNTHETIC", "query": "q1"}\n{"id": "case-2", "classification": "SYNTHETIC", "query": "q2"}\n')

    target = MockTelemetryTarget(
        latency_ms=45.2,
        tokens_in=120,
        tokens_out=30,
        cost_usd=Decimal("0.000450"),
        cost_basis=CostBasis.ESTIMATED,
    )

    plan = create_execution_plan(["mock-telemetry"], ds_file, is_live=False)
    runner = GenericRunner(db=temp_db)
    results = runner.execute_plan(
        plan,
        {"mock-telemetry": target},
        [
            {"id": "case-1", "classification": "SYNTHETIC", "query": "q1"},
            {"id": "case-2", "classification": "SYNTHETIC", "query": "q2"},
        ],
    )

    assert len(results) == 1
    run_id = results[0].run_id

    repo = TraceRepository(db=temp_db)
    traces = repo.get_traces_for_run(run_id, include_spans=True)
    assert len(traces) == 2

    # Validate case 1 trace
    tr1 = next(t for t in traces if t.case_id == "case-1")
    assert tr1.target_id == "mock-telemetry"
    assert tr1.status == SpanStatus.OK
    assert len(tr1.spans) == 1

    root1 = tr1.spans[0]
    assert root1.trace_id == tr1.trace_id
    assert root1.parent_span_id is None
    assert root1.kind == SpanKind.LLM
    assert root1.status == SpanStatus.OK
    assert root1.duration_ms == 45.2
    assert root1.prompt_tokens == 120
    assert root1.completion_tokens == 30
    assert root1.total_tokens == 150
    assert root1.cost_usd == "0.000450"
    assert root1.cost_basis == "ESTIMATED"

    # Validate case 2 trace
    tr2 = next(t for t in traces if t.case_id == "case-2")
    assert tr2.trace_id != tr1.trace_id
    assert tr2.case_id == "case-2"
    assert len(tr2.spans) == 1


# =============================================================================
# 2. Strict 'Null is not 0' Invariant on Traces & Spans
# =============================================================================


def test_generic_runner_preserves_null_is_not_zero_telemetry(tmp_path: Path, temp_db: DatabaseManager):
    """Unmeasured tokens, cost, and duration remain None; measured 0 is preserved."""
    ds_file = tmp_path / "ds.jsonl"
    ds_file.write_text('{"id": "c-unmeasured", "classification": "SYNTHETIC"}\n{"id": "c-zero", "classification": "SYNTHETIC"}\n')

    # Target 1: Unmeasured telemetry
    target_unmeasured = MockTelemetryTarget(
        target_id="target-unmeasured",
        latency_ms=None,
        tokens_in=None,
        tokens_out=None,
        cost_usd=None,
        cost_basis=CostBasis.UNAVAILABLE,
    )

    # Target 2: Measured 0 telemetry
    target_zero = MockTelemetryTarget(
        target_id="target-zero",
        latency_ms=0.0,
        tokens_in=0,
        tokens_out=0,
        cost_usd=Decimal("0.000000"),
        cost_basis=CostBasis.ACTUAL,
    )

    runner = GenericRunner(db=temp_db)

    # Run unmeasured
    plan1 = create_execution_plan(["target-unmeasured"], ds_file, is_live=False)
    r1 = runner.execute_plan(plan1, {"target-unmeasured": target_unmeasured}, [{"id": "c-unmeasured", "classification": "SYNTHETIC"}])
    tr1 = temp_db.get_traces_for_run(r1[0].run_id, include_spans=True)[0]
    sp1 = tr1.spans[0]
    assert sp1.prompt_tokens is None
    assert sp1.completion_tokens is None
    assert sp1.total_tokens is None
    assert sp1.cost_usd is None

    # Run measured 0
    plan2 = create_execution_plan(["target-zero"], ds_file, is_live=False)
    r2 = runner.execute_plan(plan2, {"target-zero": target_zero}, [{"id": "c-zero", "classification": "SYNTHETIC"}])
    tr2 = temp_db.get_traces_for_run(r2[0].run_id, include_spans=True)[0]
    sp2 = tr2.spans[0]
    assert sp2.duration_ms == 0.0
    assert sp2.prompt_tokens == 0
    assert sp2.completion_tokens == 0
    assert sp2.total_tokens == 0
    assert sp2.cost_usd == "0.000000"
    assert sp2.cost_basis == "ACTUAL"


# =============================================================================
# 3. Trajectory Linking & Hierarchy Formation
# =============================================================================


def test_generic_runner_stitches_trajectory_spans(tmp_path: Path, temp_db: DatabaseManager):
    """Child trajectory spans are dynamically bound to trace_id and linked to root_span."""
    ds_file = tmp_path / "ds.jsonl"
    ds_file.write_text('{"id": "c1", "classification": "SYNTHETIC"}\n')

    # Emit two unparented trajectory spans
    span_retrieval = Span(
        trace_id="pending",
        span_id="sp-ret-1",
        name="retrieval:vector_index",
        kind=SpanKind.RETRIEVAL,
        status=SpanStatus.OK,
        duration_ms=15.0,
        attributes={"top_k": 3},
    )
    span_tool = Span(
        trace_id="pending",
        span_id="sp-tool-1",
        name="tool:calc",
        kind=SpanKind.TOOL,
        status=SpanStatus.OK,
        duration_ms=8.5,
        attributes={"expr": "2+2"},
    )

    target = MockTelemetryTarget(
        target_id="mock-agent",
        latency_ms=120.0,
        trajectory=[span_retrieval, span_tool],
    )

    plan = create_execution_plan(["mock-agent"], ds_file, is_live=False)
    runner = GenericRunner(db=temp_db)
    res = runner.execute_plan(plan, {"mock-agent": target}, [{"id": "c1", "classification": "SYNTHETIC"}])

    trace = temp_db.get_traces_for_run(res[0].run_id, include_spans=True)[0]
    assert len(trace.spans) == 3

    root_spans = trace.get_root_spans()
    assert len(root_spans) == 1
    root = root_spans[0]
    assert root.name == "mock-agent"

    children = trace.get_child_spans(root.span_id)
    assert len(children) == 2
    assert {c.span_id for c in children} == {"sp-ret-1", "sp-tool-1"}
    for c in children:
        assert c.trace_id == trace.trace_id
        assert c.parent_span_id == root.span_id


def test_generic_runner_preserves_nested_multi_level_trajectory(tmp_path: Path, temp_db: DatabaseManager):
    """Multi-level trajectory trees (root -> step -> tool) preserve nested parent relationships."""
    ds_file = tmp_path / "ds.jsonl"
    ds_file.write_text('{"id": "c1", "classification": "SYNTHETIC"}\n')

    # Step span has no parent (will attach to root)
    step_span = Span(
        trace_id="pending",
        span_id="sp-step-node",
        name="workflow_step:agent_reasoning",
        kind=SpanKind.WORKFLOW_STEP,
        status=SpanStatus.OK,
    )
    # Tool span explicitly references step_span as parent
    tool_span = Span(
        trace_id="pending",
        span_id="sp-sub-tool",
        parent_span_id="sp-step-node",
        name="tool:search",
        kind=SpanKind.TOOL,
        status=SpanStatus.OK,
    )

    target = MockTelemetryTarget(
        target_id="complex-flow",
        trajectory=[step_span, tool_span],
    )

    plan = create_execution_plan(["complex-flow"], ds_file, is_live=False)
    runner = GenericRunner(db=temp_db)
    res = runner.execute_plan(plan, {"complex-flow": target}, [{"id": "c1", "classification": "SYNTHETIC"}])

    trace = temp_db.get_traces_for_run(res[0].run_id, include_spans=True)[0]
    root = trace.get_root_spans()[0]

    # Level 1 children (children of root)
    level1 = trace.get_child_spans(root.span_id)
    assert len(level1) == 1
    assert level1[0].span_id == "sp-step-node"

    # Level 2 children (children of step_span)
    level2 = trace.get_child_spans("sp-step-node")
    assert len(level2) == 1
    assert level2[0].span_id == "sp-sub-tool"
    assert level2[0].parent_span_id == "sp-step-node"


# =============================================================================
# 4. Connector Trajectory Emission Tests
# =============================================================================


def test_mcp_tool_target_trajectory_emission(tmp_path: Path, temp_db: DatabaseManager):
    """McpToolTarget attaches a SpanKind.TOOL span with tool latency and arguments."""
    from runport.connectors.mcp import McpToolTarget
    fixture_script = str(Path(__file__).parent / "fixtures" / "mcp_fixture_server.py")

    target = McpToolTarget(
        target_id="mcp-echo-target",
        name="MCP Echo Target",
        command=["python3", fixture_script],
        timeout_seconds=5.0,
    )

    try:
        res = target.execute({"tool": "echo", "arguments": {"text": "trace verification"}})
        assert res.status == TargetStatus.SUCCESS
        assert res.trajectory is not None
        assert len(res.trajectory) == 1

        tool_span = res.trajectory[0]
        assert tool_span.kind == SpanKind.TOOL
        assert tool_span.name == "mcp:echo"
        assert tool_span.status == SpanStatus.OK
        assert tool_span.duration_ms is not None
        assert tool_span.attributes["tool"] == "echo"
        assert tool_span.attributes["arguments"] == {"text": "trace verification"}

        # Now execute through GenericRunner
        ds_file = tmp_path / "ds.jsonl"
        ds_file.write_text('{"id": "mcp-c1", "classification": "SYNTHETIC", "tool": "echo", "arguments": {"text": "runner test"}}\n')
        plan = create_execution_plan(["mcp-echo-target"], ds_file, is_live=False)
        runner = GenericRunner(db=temp_db)
        r = runner.execute_plan(
            plan,
            {"mcp-echo-target": target},
            [{"id": "mcp-c1", "classification": "SYNTHETIC", "tool": "echo", "arguments": {"text": "runner test"}}],
        )

        trace = temp_db.get_traces_for_run(r[0].run_id, include_spans=True)[0]
        assert len(trace.spans) == 2  # root tool target span + child tool execution span
        root = trace.get_root_spans()[0]
        assert root.kind == SpanKind.TOOL
        child = trace.get_child_spans(root.span_id)[0]
        assert child.name == "mcp:echo"
        assert child.kind == SpanKind.TOOL
    finally:
        target.close()


def test_dify_node_spans_conversion():
    """_build_dify_node_spans accurately maps Dify node execution telemetry."""
    node_records = [
        {
            "id": "node-ret-1",
            "node_type": "knowledge-retrieval",
            "title": "Knowledge Search",
            "status": "succeeded",
            "elapsed_time": 0.25,  # seconds
            "execution_metadata": {"total_tokens": 80},
            "inputs": {"query": "sample query"},
            "outputs": {"chunks": 2},
        },
        {
            "id": "node-llm-1",
            "node_type": "llm",
            "title": "Generator",
            "status": "succeeded",
            "elapsed_time": 0.65,
            "execution_metadata": {"prompt_tokens": 100, "completion_tokens": 40, "total_tokens": 140},
            "outputs": {"text": "generated output"},
        },
    ]

    spans = _build_dify_node_spans(node_records)
    assert len(spans) == 2

    s1 = spans[0]
    assert s1.name == "Knowledge Search"
    assert s1.kind == SpanKind.RETRIEVAL
    assert s1.status == SpanStatus.OK
    assert s1.duration_ms == 250.0
    assert s1.total_tokens == 80
    assert s1.attributes["inputs"] == {"query": "sample query"}

    s2 = spans[1]
    assert s2.name == "Generator"
    assert s2.kind == SpanKind.LLM
    assert s2.status == SpanStatus.OK
    assert s2.duration_ms == 650.0
    assert s2.prompt_tokens == 100
    assert s2.completion_tokens == 40
    assert s2.total_tokens == 140


def test_rag_pipeline_target_trajectory_emission():
    """RagPipelineTarget emits decoupled RETRIEVAL and LLM spans."""
    class FakeRetriever(BaseRetriever):
        def __init__(self):
            self.retriever_id = "test-bm25"

        def retrieve(self, case, top_k=2):
            return RetrievalResult(
                retriever_id=self.retriever_id,
                chunks=["doc passage 1", "doc passage 2"],
                retrieved_record_ids=["r1", "r2"],
                hit_rate=1.0,
                precision=1.0,
                latency_ms=12.4,
            )

    target = RagPipelineTarget(
        model_id="gpt-4o-mini",
        retriever=FakeRetriever(),
        adapter=LiveFakeProvider({"c-rag-1": "Answer based on context"}),
        top_k=2,
    )

    case_payload = {
        "id": "c-rag-1",
        "query": "Where is the lab located?",
        "expected_answer": "In Building 4",
        "classification": "SYNTHETIC",
    }
    res = target.execute(case_payload)

    assert res.status == TargetStatus.SUCCESS
    assert res.trajectory is not None
    assert len(res.trajectory) == 2

    ret_span = res.trajectory[0]
    assert ret_span.kind == SpanKind.RETRIEVAL
    assert ret_span.name == "retrieval:test-bm25"
    assert ret_span.duration_ms == 12.4
    assert ret_span.attributes["chunks_count"] == 2

    llm_span = res.trajectory[1]
    assert llm_span.kind == SpanKind.LLM
    assert llm_span.name == "llm:gpt-4o-mini"
    assert llm_span.prompt_tokens == 100
    assert llm_span.completion_tokens == 20
    assert llm_span.cost_usd == "0.000100"
    assert llm_span.cost_basis == "ESTIMATED"


# =============================================================================
# 5. Security & Secret Scrubbing on Traces
# =============================================================================


def test_automatic_secret_scrubbing_on_traces_and_spans(tmp_path: Path, temp_db: DatabaseManager):
    """API keys, Bearer tokens, and secrets in metadata or errors are scrubbed from persisted spans."""
    ds_file = tmp_path / "ds.jsonl"
    ds_file.write_text('{"id": "sec-1", "classification": "SYNTHETIC"}\n')

    secret_key = "sk-ant-api03-TOPSECRETKEY123456789012345"
    bearer = "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.secretpayload"

    target = MockTelemetryTarget(
        target_id="leaky-target",
        status=TargetStatus.FAILED,
        metadata={"api_key": secret_key, "auth_header": bearer, "safe_field": "public_data"},
        error_message=f"Request failed with {secret_key}",
    )

    plan = create_execution_plan(["leaky-target"], ds_file, is_live=False)
    runner = GenericRunner(db=temp_db)
    res = runner.execute_plan(plan, {"leaky-target": target}, [{"id": "sec-1", "classification": "SYNTHETIC"}])

    trace = temp_db.get_traces_for_run(res[0].run_id, include_spans=True)[0]
    span = trace.spans[0]

    # Span error must be scrubbed
    assert secret_key not in span.error
    assert "[REDACTED_API_KEY]" in span.error

    # Span attributes must be scrubbed
    attrs = span.attributes.get("metadata", {})
    assert attrs["api_key"] == "[REDACTED_SECRET]"
    assert secret_key not in json.dumps(attrs)
    assert attrs["safe_field"] == "public_data"


# =============================================================================
# 6. Status and Execution Failures
# =============================================================================


def test_error_and_timeout_status_mapping(tmp_path: Path, temp_db: DatabaseManager):
    """TargetStatus.TIMEOUT maps to SpanStatus.TIMEOUT; failures map to SpanStatus.ERROR."""
    ds_file = tmp_path / "ds.jsonl"
    ds_file.write_text('{"id": "t1", "classification": "SYNTHETIC"}\n{"id": "f1", "classification": "SYNTHETIC"}\n')

    timeout_target = MockTelemetryTarget(target_id="timeout-target", status=TargetStatus.TIMEOUT, error_message="Socket timed out")
    failed_target = MockTelemetryTarget(target_id="fail-target", status=TargetStatus.FAILED, error_message="Internal error 500")

    runner = GenericRunner(db=temp_db)

    # Test Timeout
    plan_t = create_execution_plan(["timeout-target"], ds_file, is_live=False)
    r_t = runner.execute_plan(plan_t, {"timeout-target": timeout_target}, [{"id": "t1", "classification": "SYNTHETIC"}])
    tr_t = temp_db.get_traces_for_run(r_t[0].run_id, include_spans=True)[0]
    assert tr_t.status == SpanStatus.TIMEOUT
    assert tr_t.spans[0].status == SpanStatus.TIMEOUT
    assert tr_t.spans[0].error == "Socket timed out"

    # Test Failed
    plan_f = create_execution_plan(["fail-target"], ds_file, is_live=False)
    r_f = runner.execute_plan(plan_f, {"fail-target": failed_target}, [{"id": "f1", "classification": "SYNTHETIC"}])
    tr_f = temp_db.get_traces_for_run(r_f[0].run_id, include_spans=True)[0]
    assert tr_f.status == SpanStatus.ERROR
    assert tr_f.spans[0].status == SpanStatus.ERROR
    assert tr_f.spans[0].error == "Internal error 500"


def test_unresolved_spend_halt_preserves_executed_traces(tmp_path: Path, temp_db: DatabaseManager):
    """When execution halts due to unresolved spend, already executed case traces are preserved in SQLite."""
    class SteppedTarget(Target):
        def __init__(self):
            super().__init__(
                target_id="stepped-target",
                name="Stepped Target",
                target_type=TargetType.RAW_MODEL,
                pricing=TargetPricing(fixed_usd_per_request=Decimal("0.05")),
                billing=BillingMode.BILLABLE,
            )
            self.step = 0

        def execute(self, payload: Dict[str, Any], context=None) -> TargetResult:
            self.step += 1
            if self.step == 1:
                return TargetResult(
                    target_id=self.target_id,
                    status=TargetStatus.SUCCESS,
                    output_text="Success 1",
                    cost_usd=Decimal("0.05"),
                    cost_basis=CostBasis.ESTIMATED,
                    provenance="LIVE",
                )
            # Step 2: Billable target returns no cost -> halts run
            return TargetResult(
                target_id=self.target_id,
                status=TargetStatus.SUCCESS,
                output_text="Success 2 without cost",
                cost_usd=None,
                cost_basis=CostBasis.UNRESOLVED,
                provenance="LIVE",
            )

    ds_file = tmp_path / "ds.jsonl"
    ds_file.write_text('{"id": "c1", "classification": "SYNTHETIC"}\n{"id": "c2", "classification": "SYNTHETIC"}\n{"id": "c3", "classification": "SYNTHETIC"}\n')

    plan = create_execution_plan(["stepped-target"], ds_file, is_live=True)
    approver = TokenApprover(token=plan.fingerprint, enabled=True)
    target = SteppedTarget()
    runner = GenericRunner(db=temp_db)

    results = runner.execute_plan(
        plan,
        {"stepped-target": target},
        [
            {"id": "c1", "classification": "SYNTHETIC"},
            {"id": "c2", "classification": "SYNTHETIC"},
            {"id": "c3", "classification": "SYNTHETIC"},
        ],
        approver=approver,
    )

    res = results[0]
    assert res.halt_kind == "unresolved_spend"
    assert len(res.case_results) == 2  # c3 was not sent

    # Verify both executed cases have traces stored in SQLite
    traces = temp_db.get_traces_for_run(res.run_id, include_spans=True)
    assert len(traces) == 2
    case_ids = {t.case_id for t in traces}
    assert case_ids == {"c1", "c2"}


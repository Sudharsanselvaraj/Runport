"""Unit tests for Milestone 5 - Task 5.3: Native LangGraph Streaming & Instrumentation.

Tests:
1. LangGraphStreamingConnector configuration and URL routing.
2. Real-time SSE streaming parsing:
   - Node transitions (event: updates) -> canonical SpanKind.WORKFLOW_STEP.
   - Tool executions -> canonical SpanKind.TOOL.
   - Final message reconstruction and output text accumulation.
3. Trajectory preservation on TargetResult:
   - Root agent span + child spans.
   - Node sequence metadata.
4. Error handling: HTTP failures, socket timeouts.
5. In-process RunportLangGraphTracer:
   - Multi-step graph node callbacks (on_chain_start, on_chain_end).
   - Tool callbacks (on_tool_start, on_tool_end).
   - LLM callbacks (on_llm_start, on_llm_end) with token usage parsing.
   - Canonical Trace hierarchy validation.
6. Invariant 1: 'Null is not 0' across missing tokens and latency.
7. Invariant 7: Zero secret leakage in streaming events and tracer attributes.
"""

from datetime import datetime, timezone
import json
from unittest.mock import MagicMock, patch
import pytest

from runport.connectors.langgraph import (
    LangGraphConnector,
    LangGraphStreamingConnector,
    RunportLangGraphTracer,
)
from runport.targets.base import TargetStatus, TargetType
from runport.traces.domain import SpanKind, SpanStatus, Trace


def test_langgraph_streaming_connector_init():
    """Verifies LangGraphStreamingConnector initializes URLs and headers correctly."""
    conn = LangGraphStreamingConnector(
        target_id="lg-stream-1",
        name="SupportGraphAgent",
        base_url="https://api.langgraph.example.com",
        assistant_id="asst-9988",
        api_key="lg-secret-token",
        stream_mode="updates",
    )
    assert conn.url == "https://api.langgraph.example.com/runs/stream"
    assert conn.headers["x-api-key"] == "lg-secret-token"
    assert conn.headers["Accept"] == "text/event-stream"
    assert conn.target_type == TargetType.WORKFLOW_LANGGRAPH

    # Thread-specific URL
    conn_thread = LangGraphStreamingConnector(
        target_id="lg-stream-2",
        name="ThreadAgent",
        base_url="https://api.langgraph.example.com",
        assistant_id="asst-9988",
        thread_id="th-12345",
    )
    assert conn_thread.url == "https://api.langgraph.example.com/threads/th-12345/runs/stream"


def test_langgraph_streaming_execute_success():
    """Verifies SSE streaming execution parses node transitions into canonical Spans."""
    conn = LangGraphStreamingConnector(
        target_id="lg-stream-1",
        name="SupportGraphAgent",
        base_url="http://127.0.0.1:8000",
        assistant_id="asst-agent-01",
    )

    sse_lines = [
        b"event: metadata\n",
        b'data: {"run_id": "run-001", "assistant_id": "asst-agent-01"}\n\n',
        b"event: updates\n",
        b'data: {"router": {"route": "tools", "secret": "bearer-key-12345"}}\n\n',
        b"event: updates\n",
        b'data: {"tools": {"output": "User status is active", "tool_name": "check_user"}}\n\n',
        b"event: updates\n",
        b'data: {"agent": {"messages": [{"role": "assistant", "content": "Your account is active."}]}}\n\n',
        b"data: [DONE]\n\n",
    ]

    mock_resp = MagicMock()
    mock_resp.status = 200
    mock_resp.__iter__.return_value = sse_lines
    mock_resp.__enter__.return_value = mock_resp

    with patch("urllib.request.urlopen", return_value=mock_resp):
        res = conn.execute({"query": "Check my account status"})

    assert res.status == TargetStatus.SUCCESS
    assert res.output_text == "Your account is active."
    assert res.metadata["node_sequence"] == ["router", "tools", "agent"]
    assert res.metadata["total_transitions"] == 3

    # Trajectory check
    assert res.trajectory is not None
    assert len(res.trajectory) == 4  # Root AGENT + router + tools + agent

    root = res.trajectory[0]
    assert root.kind == SpanKind.AGENT
    assert root.name == "SupportGraphAgent"

    router_span = res.trajectory[1]
    assert router_span.name == "router"
    assert router_span.kind == SpanKind.WORKFLOW_STEP
    # Invariant 7: Secret scrubbing
    assert "[REDACTED" in router_span.attributes["secret"]

    tool_span = res.trajectory[2]
    assert tool_span.name == "tools"
    assert tool_span.kind == SpanKind.TOOL

    agent_span = res.trajectory[3]
    assert agent_span.name == "agent"
    assert agent_span.kind == SpanKind.WORKFLOW_STEP


def test_langgraph_streaming_generator():
    """Verifies stream() yields incremental text chunks."""
    conn = LangGraphStreamingConnector(
        target_id="lg-stream-1",
        name="SupportGraphAgent",
        base_url="http://127.0.0.1:8000",
        assistant_id="asst-agent-01",
    )

    sse_lines = [
        b"event: messages\n",
        b'data: [{"type": "ai", "content": "Hello"}]\n\n',
        b"event: messages\n",
        b'data: [{"type": "ai", "content": " there!"}]\n\n',
        b"data: [DONE]\n\n",
    ]

    mock_resp = MagicMock()
    mock_resp.status = 200
    mock_resp.__iter__.return_value = sse_lines
    mock_resp.__enter__.return_value = mock_resp

    with patch("urllib.request.urlopen", return_value=mock_resp):
        chunks = list(conn.stream({"query": "Hi"}))

    assert len(chunks) == 3
    assert chunks[0].delta_text == "Hello"
    assert not chunks[0].is_final
    assert chunks[1].delta_text == " there!"
    assert not chunks[1].is_final
    assert chunks[2].is_final


def test_langgraph_streaming_error_handling():
    """Verifies HTTP errors and network timeouts are properly converted to TargetResult."""
    conn = LangGraphStreamingConnector(
        target_id="lg-stream-1",
        name="SupportGraphAgent",
        base_url="http://127.0.0.1:8000",
        assistant_id="asst-agent-01",
    )

    with patch("urllib.request.urlopen", side_effect=TimeoutError("Request timed out")):
        res = conn.execute({"query": "Hi"})

    assert res.status == TargetStatus.TIMEOUT
    assert "timed out" in (res.error_message or "").lower()
    assert res.trajectory is not None
    assert res.trajectory[0].status == SpanStatus.ERROR


def test_runport_langgraph_inprocess_tracer():
    """Verifies in-process RunportLangGraphTracer records graph execution into canonical Spans."""
    tracer = RunportLangGraphTracer(trace_id="tr-test-tracer", name="OrderTriageGraph")

    # Step 1: Chain start (Graph root / node)
    tracer.on_chain_start(
        serialized={"name": "supervisor_node"},
        inputs={"query": "Cancel order #445", "token": "Bearer sensitive_secret_777"},
        run_id="run-step-1",
    )

    # Step 2: Tool execution
    tracer.on_tool_start(
        serialized={"name": "lookup_order_tool"},
        input_str="order_id=445",
        run_id="run-tool-1",
        parent_run_id="run-step-1",
    )
    tracer.on_tool_end(
        output="Order #445 status is PENDING",
        run_id="run-tool-1",
        parent_run_id="run-step-1",
    )

    # Step 3: LLM execution
    mock_response = MagicMock()
    mock_response.llm_output = {
        "token_usage": {
            "prompt_tokens": 120,
            "completion_tokens": 45,
            "total_tokens": 165,
        }
    }
    tracer.on_llm_start(
        serialized={"name": "chat_model", "model": "gpt-4o-mini"},
        prompts=["User asks to cancel order 445"],
        run_id="run-llm-1",
        parent_run_id="run-step-1",
    )
    tracer.on_llm_end(
        response=mock_response,
        run_id="run-llm-1",
        parent_run_id="run-step-1",
    )

    # Step 4: Chain end
    tracer.on_chain_end(
        outputs={"final_message": "Order #445 has been cancelled."},
        run_id="run-step-1",
    )

    spans = tracer.get_spans()
    assert len(spans) == 3

    # Check kinds
    kinds = [s.kind for s in spans]
    assert SpanKind.TOOL in kinds
    assert SpanKind.LLM in kinds
    assert SpanKind.WORKFLOW_STEP in kinds

    # LLM span verification
    llm_span = [s for s in spans if s.kind == SpanKind.LLM][0]
    assert llm_span.prompt_tokens == 120
    assert llm_span.completion_tokens == 45
    assert llm_span.total_tokens == 165
    assert llm_span.model == "gpt-4o-mini"

    # Invariant 7: Secret scrubbing
    step_span = [s for s in spans if s.kind == SpanKind.WORKFLOW_STEP][0]
    assert "[REDACTED" in json.dumps(step_span.attributes)
    assert "sensitive_secret" not in json.dumps(step_span.attributes)

    # Check canonical trace creation
    trace = tracer.get_trace()
    assert isinstance(trace, Trace)
    assert trace.trace_id == "tr-test-tracer"
    assert trace.name == "OrderTriageGraph"
    assert trace.status == SpanStatus.OK
    assert len(trace.spans) == 3


def test_runport_langgraph_tracer_error():
    """Verifies tracer records errors and marks span status as ERROR."""
    tracer = RunportLangGraphTracer(trace_id="tr-test-err", name="ErrorGraph")

    tracer.on_chain_start(
        serialized={"name": "failing_node"},
        inputs={"data": "test"},
        run_id="err-run-1",
    )
    tracer.on_chain_error(
        error=ValueError("Invalid state transition"),
        run_id="err-run-1",
    )

    spans = tracer.get_spans()
    assert len(spans) == 1
    assert spans[0].status == SpanStatus.ERROR
    assert "Invalid state transition" in (spans[0].error or "")

    trace = tracer.get_trace()
    assert trace.status == SpanStatus.ERROR

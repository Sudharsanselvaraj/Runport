"""Unit tests for Phase 6: Universal Developer Instrumentation API.

Tests:
1. Synchronous @trace decorator with function args and return value capture.
2. Asynchronous @trace decorator with coroutines.
3. Nested trace hierarchy: parent-child relationships across function calls.
4. Error capturing and sanitization: exceptions mark span as ERROR.
5. start_trace / start_span context managers and add_event / set_span_attribute.
6. wrap_openai client wrapper extracting token usage and choices.
7. wrap_anthropic client wrapper extracting input/output tokens and content blocks.
8. Strict enforcement of 'Null is not 0' invariant when usage telemetry is absent.
9. Zero secret leakage: credentials scrubbed from args, kwargs, and outputs.
"""

import asyncio
from datetime import datetime, timezone
import json
from pathlib import Path
from unittest.mock import MagicMock
import pytest

from runport.core.config import settings
from runport.instrumentation import (
    add_event,
    get_current_span,
    get_current_trace,
    set_span_attribute,
    start_span,
    start_trace,
    trace,
    wrap_anthropic,
    wrap_openai,
)
from runport.storage.db import DatabaseManager
from runport.traces.domain import SpanKind, SpanStatus
from runport.traces.repository import TraceRepository


@pytest.fixture
def test_db(tmp_path: Path, monkeypatch):
    """Sets up an isolated SQLite database for instrumentation tests."""
    db_file = tmp_path / "instrumentation.db"
    monkeypatch.setattr(type(settings), "db_path", property(lambda self: db_file))
    db = DatabaseManager(db_file)
    db.init_db()
    return db


def test_sync_trace_decorator(test_db):
    """Verifies synchronous @trace captures args, output, duration, and persists trace."""
    repo = TraceRepository(db=test_db)

    @trace(name="CalculateSquare", kind=SpanKind.WORKFLOW_STEP, save_on_exit=True)
    def calc_square(x: int, token: str = "Bearer sk-secret-12345") -> int:
        return x * x

    result = calc_square(7, token="Bearer sk-secret-1234567890abcdef")
    assert result == 49

    traces = repo.list_traces(limit=10, include_spans=True)
    assert len(traces) == 1
    t = traces[0]
    assert t.name == "CalculateSquare"
    assert t.status == SpanStatus.OK
    assert len(t.spans) == 1

    s = t.spans[0]
    assert s.name == "CalculateSquare"
    assert s.kind == SpanKind.WORKFLOW_STEP
    assert s.attributes["output"] == 49
    # Invariant 7: Secret scrubbing
    assert "[REDACTED" in json.dumps(s.attributes["kwargs"])
    assert "sk-secret" not in json.dumps(s.attributes)


@pytest.mark.anyio
async def test_async_trace_decorator(test_db):
    """Verifies asynchronous @trace decorator works with coroutines."""
    repo = TraceRepository(db=test_db)

    @trace(name="AsyncFetcher", kind=SpanKind.AGENT, save_on_exit=True)
    async def fetch_data(item_id: str) -> dict:
        await asyncio.sleep(0.01)
        return {"id": item_id, "status": "loaded"}

    res = await fetch_data("item-42")
    assert res == {"id": "item-42", "status": "loaded"}

    traces = repo.list_traces(limit=10, include_spans=True)
    assert len(traces) == 1
    assert traces[0].spans[0].kind == SpanKind.AGENT
    assert traces[0].spans[0].attributes["output"]["status"] == "loaded"


def test_nested_span_hierarchy(test_db):
    """Verifies nested function calls build valid parent-child span hierarchy."""
    repo = TraceRepository(db=test_db)

    @trace(name="ChildStep", kind=SpanKind.TOOL)
    def step_two(val: str) -> str:
        set_span_attribute("processed_by", "worker-1")
        add_event("substep_complete", {"stage": "validation"})
        return f"processed_{val}"

    @trace(name="ParentWorkflow", kind=SpanKind.WORKFLOW_STEP, save_on_exit=True)
    def step_one(raw: str) -> str:
        return step_two(raw)

    out = step_one("data")
    assert out == "processed_data"

    traces = repo.list_traces(limit=10, include_spans=True)
    assert len(traces) == 1
    t = traces[0]
    assert len(t.spans) == 2

    parent_span = [s for s in t.spans if s.name == "ParentWorkflow"][0]
    child_span = [s for s in t.spans if s.name == "ChildStep"][0]

    assert parent_span.parent_span_id is None
    assert child_span.parent_span_id == parent_span.span_id
    assert child_span.kind == SpanKind.TOOL
    assert child_span.attributes["processed_by"] == "worker-1"
    assert len(child_span.events) == 1
    assert child_span.events[0].name == "substep_complete"


def test_error_capture_in_trace(test_db):
    """Verifies exceptions are sanitized and span status is set to ERROR."""
    repo = TraceRepository(db=test_db)

    @trace(name="FailingOperation", save_on_exit=True)
    def boom():
        raise RuntimeError("Fatal connection failure: api_key=secret-998877")

    with pytest.raises(RuntimeError):
        boom()

    traces = repo.list_traces(limit=10, include_spans=True)
    assert len(traces) == 1
    t = traces[0]
    assert t.status == SpanStatus.ERROR
    assert t.spans[0].status == SpanStatus.ERROR
    assert "Fatal connection failure" in t.spans[0].error
    # Invariant 7: Secret scrubbing
    assert "secret-998877" not in t.spans[0].error


def test_wrap_openai():
    """Verifies wrap_openai intercepts chat completion and records canonical LLM span."""
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.usage.prompt_tokens = 110
    mock_response.usage.completion_tokens = 45
    mock_response.usage.total_tokens = 155

    choice_mock = MagicMock()
    choice_mock.message.content = "Here is the summary."
    mock_response.choices = [choice_mock]

    mock_client.chat.completions.create.return_value = mock_response

    wrapped = wrap_openai(mock_client)

    with start_trace(name="OpenAITestTrace") as t:
        resp = wrapped.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": "Summarize document"}],
            temperature=0.3,
        )

    assert resp == mock_response
    assert len(t.spans) == 1
    s = t.spans[0]
    assert s.kind == SpanKind.LLM
    assert s.model == "gpt-4o-mini"
    assert s.prompt_tokens == 110
    assert s.completion_tokens == 45
    assert s.total_tokens == 155
    assert s.attributes["output"] == "Here is the summary."


def test_wrap_anthropic():
    """Verifies wrap_anthropic intercepts messages.create and records canonical LLM span."""
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.usage.input_tokens = 220
    mock_response.usage.output_tokens = 80

    block_mock = MagicMock()
    block_mock.text = "Anthropic generated response"
    mock_response.content = [block_mock]

    mock_client.messages.create.return_value = mock_response

    wrapped = wrap_anthropic(mock_client)

    with start_trace(name="AnthropicTestTrace") as t:
        resp = wrapped.messages.create(
            model="claude-3-5-sonnet",
            messages=[{"role": "user", "content": "Hello Claude"}],
            max_tokens=500,
        )

    assert resp == mock_response
    assert len(t.spans) == 1
    s = t.spans[0]
    assert s.kind == SpanKind.LLM
    assert s.model == "claude-3-5-sonnet"
    assert s.prompt_tokens == 220
    assert s.completion_tokens == 80
    assert s.total_tokens == 300
    assert "Anthropic generated response" in s.attributes["output"]


def test_wrap_unmeasured_usage_null_is_not_zero():
    """Verifies Invariant 1 ('Null is not 0'): missing tokens stay None."""
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.usage = None  # Telemetry missing
    mock_response.choices = []
    mock_client.chat.completions.create.return_value = mock_response

    wrapped = wrap_openai(mock_client)

    with start_trace(name="UnmeasuredTrace") as t:
        wrapped.chat.completions.create(model="custom-local-model", messages=[])

    s = t.spans[0]
    assert s.prompt_tokens is None
    assert s.completion_tokens is None
    assert s.total_tokens is None

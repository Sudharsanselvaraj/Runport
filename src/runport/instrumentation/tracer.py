"""Universal developer instrumentation API for Runport.

Enables tracing of arbitrary Python code, agents, tool calls, and LLM calls
into canonical Runport Traces and Spans.

Usage:
    from runport.instrumentation import trace, start_trace, start_span, add_event
    from runport.traces.domain import SpanKind

    @trace(name="MyAgentStep", kind=SpanKind.AGENT)
    def run_agent(query: str):
        with start_span("SearchDatabase", kind=SpanKind.TOOL):
            add_event("cache_check", {"hit": False})
            results = do_search(query)
        return results
"""

from __future__ import annotations

from contextlib import contextmanager
import contextvars
from datetime import datetime, timezone
import functools
import inspect
import time
from typing import Any, Callable, Dict, List, Optional, Tuple, TypeVar, Union
import uuid

from runport.core.config import settings
from runport.providers.base import scrub_secrets
from runport.storage.db import DatabaseManager
from runport.traces.domain import (
    Span,
    SpanEvent,
    SpanKind,
    SpanStatus,
    Trace,
)
from runport.traces.repository import TraceRepository

F = TypeVar("F", bound=Callable[..., Any])

# Context variables for tracking active trace and span hierarchy
_current_trace: contextvars.ContextVar[Optional[Trace]] = contextvars.ContextVar("current_trace", default=None)
_current_span: contextvars.ContextVar[Optional[Span]] = contextvars.ContextVar("current_span", default=None)


def get_current_trace() -> Optional[Trace]:
    """Returns the currently active Trace in the execution context, if any."""
    return _current_trace.get()


def get_current_span() -> Optional[Span]:
    """Returns the currently active Span in the execution context, if any."""
    return _current_span.get()


@contextmanager
def start_trace(
    name: str = "execution_trace",
    run_id: Optional[str] = None,
    case_id: Optional[str] = None,
    target_id: Optional[str] = None,
    session_id: Optional[str] = None,
    attributes: Optional[Dict[str, Any]] = None,
    save_on_exit: bool = True,
    repo: Optional[TraceRepository] = None,
):
    """Context manager that starts a new root canonical Trace."""
    t0 = datetime.now(timezone.utc)
    trace_id = f"tr-{uuid.uuid4().hex[:12]}"

    clean_attrs = scrub_secrets(dict(attributes or {}))
    trace = Trace(
        trace_id=trace_id,
        run_id=run_id,
        case_id=case_id,
        target_id=target_id,
        session_id=session_id,
        name=name,
        status=SpanStatus.OK,
        start_time=t0,
        attributes=clean_attrs,
        spans=[],
        source="instrumentation",
    )

    token_trace = _current_trace.set(trace)
    try:
        yield trace
    except BaseException as e:
        trace.status = SpanStatus.ERROR
        trace.attributes["error"] = scrub_secrets(str(e))
        raise
    finally:
        trace.end_time = datetime.now(timezone.utc)
        _current_trace.reset(token_trace)
        if save_on_exit:
            try:
                active_repo = repo or TraceRepository(DatabaseManager(settings.db_path))
                active_repo.save_trace(trace)
            except Exception:
                # Tracing persistence must never crash the underlying application
                pass


@contextmanager
def start_span(
    name: str,
    kind: SpanKind = SpanKind.WORKFLOW_STEP,
    attributes: Optional[Dict[str, Any]] = None,
    provider: Optional[str] = None,
    model: Optional[str] = None,
):
    """Context manager that starts a child Span within the current active Trace."""
    active_trace = _current_trace.get()
    parent_span = _current_span.get()

    created_trace = False
    trace_token = None

    # Auto-initialize trace if not present
    if active_trace is None:
        t_init = datetime.now(timezone.utc)
        active_trace = Trace(
            trace_id=f"tr-{uuid.uuid4().hex[:12]}",
            name=name,
            status=SpanStatus.OK,
            start_time=t_init,
            spans=[],
            source="instrumentation",
        )
        trace_token = _current_trace.set(active_trace)
        created_trace = True

    t0_dt = datetime.now(timezone.utc)
    t0_wall = time.perf_counter()
    span_id = f"span-{uuid.uuid4().hex[:8]}"

    clean_attrs = scrub_secrets(dict(attributes or {}))
    span = Span(
        trace_id=active_trace.trace_id,
        span_id=span_id,
        parent_span_id=parent_span.span_id if parent_span else None,
        name=name,
        kind=kind,
        status=SpanStatus.OK,
        start_time=t0_dt,
        provider=provider,
        model=model,
        attributes=clean_attrs,
        events=[],
        source="instrumentation",
    )

    active_trace.spans.append(span)
    span_token = _current_span.set(span)

    try:
        yield span
    except BaseException as e:
        span.status = SpanStatus.ERROR
        span.error = scrub_secrets(str(e))
        active_trace.status = SpanStatus.ERROR
        raise
    finally:
        t1_dt = datetime.now(timezone.utc)
        span.end_time = t1_dt
        span.duration_ms = max(0.0, (time.perf_counter() - t0_wall) * 1000.0)
        _current_span.reset(span_token)

        if created_trace and trace_token is not None:
            active_trace.end_time = t1_dt
            _current_trace.reset(trace_token)
            try:
                active_repo = TraceRepository(DatabaseManager(settings.db_path))
                active_repo.save_trace(active_trace)
            except Exception:
                pass


def add_event(name: str, attributes: Optional[Dict[str, Any]] = None) -> None:
    """Records an instant timestamped event on the current active span."""
    span = _current_span.get()
    if span is not None:
        span.events.append(
            SpanEvent(
                name=name,
                timestamp=datetime.now(timezone.utc),
                attributes=scrub_secrets(attributes or {}),
            )
        )


def set_span_attribute(key: str, value: Any) -> None:
    """Sets a sanitized attribute on the current active span."""
    span = _current_span.get()
    if span is not None:
        span.attributes[key] = scrub_secrets(value)


def trace(
    name: Optional[str] = None,
    kind: SpanKind = SpanKind.WORKFLOW_STEP,
    attributes: Optional[Dict[str, Any]] = None,
    save_on_exit: bool = True,
):
    """Universal decorator to trace synchronous and asynchronous functions as canonical Spans."""

    def decorator(fn: F) -> F:
        op_name = name or fn.__name__

        if inspect.iscoroutinefunction(fn):

            @functools.wraps(fn)
            async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
                is_root = _current_trace.get() is None
                call_attrs = dict(attributes or {})
                if args:
                    call_attrs["args"] = scrub_secrets(args)
                if kwargs:
                    call_attrs["kwargs"] = scrub_secrets(kwargs)

                if is_root:
                    with start_trace(name=op_name, save_on_exit=save_on_exit):
                        with start_span(name=op_name, kind=kind, attributes=call_attrs) as s:
                            result = await fn(*args, **kwargs)
                            if result is not None:
                                s.attributes["output"] = scrub_secrets(result)
                            return result
                else:
                    with start_span(name=op_name, kind=kind, attributes=call_attrs) as s:
                        result = await fn(*args, **kwargs)
                        if result is not None:
                            s.attributes["output"] = scrub_secrets(result)
                        return result

            return async_wrapper  # type: ignore

        else:

            @functools.wraps(fn)
            def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
                is_root = _current_trace.get() is None
                call_attrs = dict(attributes or {})
                if args:
                    call_attrs["args"] = scrub_secrets(args)
                if kwargs:
                    call_attrs["kwargs"] = scrub_secrets(kwargs)

                if is_root:
                    with start_trace(name=op_name, save_on_exit=save_on_exit):
                        with start_span(name=op_name, kind=kind, attributes=call_attrs) as s:
                            result = fn(*args, **kwargs)
                            if result is not None:
                                s.attributes["output"] = scrub_secrets(result)
                            return result
                else:
                    with start_span(name=op_name, kind=kind, attributes=call_attrs) as s:
                        result = fn(*args, **kwargs)
                        if result is not None:
                            s.attributes["output"] = scrub_secrets(result)
                        return result

            return sync_wrapper  # type: ignore

    return decorator

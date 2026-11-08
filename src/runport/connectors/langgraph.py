"""LangGraph agent architecture connector and instrumentation for Runport.

Milestone 5 - Task 5.3:
1. LangGraphStreamingConnector: native streaming SSE adapter capturing node transitions,
   tool calls, and model outputs as canonical child spans in real time without buffering.
2. RunportLangGraphTracer: in-process callback handler instrumenting LangGraph and
   LangChain state machines into canonical Runport Traces and Spans.
3. LangGraphConnector: legacy blocking connector pointing to /runs/wait.
4. Strict enforcement of architectural invariants:
   - 'Null is not 0': missing tokens, latency, or cost remain None.
   - Zero secret leakage: API keys, tokens, and payloads scrubbed.
"""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
import json
import re
import socket
import time
from typing import Any, Dict, Iterator, List, Optional
import urllib.error
import urllib.request
import uuid

from runport.connectors.http_workflow import HttpWorkflowConnector
from runport.providers.base import scrub_secrets
from runport.targets.base import (
    CostBasis,
    Target,
    TargetChunk,
    TargetPricing,
    TargetResult,
    TargetStatus,
    TargetType,
    billing_for_url,
)
from runport.traces.domain import (
    Span,
    SpanEvent,
    SpanKind,
    SpanStatus,
    Trace,
)


class LangGraphConnector(HttpWorkflowConnector):
    """Benchmarks LangGraph multi-agent systems via the blocking /runs/wait endpoint."""

    def __init__(
        self,
        target_id: str,
        name: str,
        base_url: str,
        assistant_id: str,
        api_key: Optional[str] = None,
        pricing: Optional[TargetPricing] = None,
        timeout_seconds: float = 60.0,
        max_retries: int = 3,
    ) -> None:
        url = f"{base_url.rstrip('/')}/runs/wait"
        headers = {}
        if api_key:
            headers["x-api-key"] = api_key

        payload_template = {
            "assistant_id": assistant_id,
            "input": {"messages": [{"role": "user", "content": "{{query}}"}]},
        }

        super().__init__(
            target_id=target_id,
            name=name,
            url=url,
            method="POST",
            headers=headers,
            payload_template=payload_template,
            output_path="messages.-1.content",
            pricing=pricing,
            timeout_seconds=timeout_seconds,
            max_retries=max_retries,
        )
        self.target_type = TargetType.WORKFLOW_LANGGRAPH


class LangGraphStreamingConnector(Target):
    """Streaming adapter for LangGraph Cloud and Server /runs/stream SSE endpoints.

    Captures node transitions, state updates, tool invocations, and LLM completions
    as canonical Runport Spans in real time.
    """

    def __init__(
        self,
        target_id: str,
        name: str,
        base_url: str,
        assistant_id: str,
        thread_id: Optional[str] = None,
        api_key: Optional[str] = None,
        pricing: Optional[TargetPricing] = None,
        timeout_seconds: float = 60.0,
        stream_mode: str = "updates",  # "updates", "values", "messages", "events"
    ) -> None:
        super().__init__(
            target_id=target_id,
            name=name,
            target_type=TargetType.WORKFLOW_LANGGRAPH,
            pricing=pricing,
            timeout_seconds=timeout_seconds,
            billing=billing_for_url(base_url),
        )
        self.base_url = base_url.rstrip("/")
        self.assistant_id = assistant_id
        self.thread_id = thread_id
        self.api_key = api_key
        self.pricing = pricing
        self.timeout_seconds = timeout_seconds
        self.stream_mode = stream_mode

        if self.thread_id:
            self.url = f"{self.base_url}/threads/{self.thread_id}/runs/stream"
        else:
            self.url = f"{self.base_url}/runs/stream"

        self.headers: Dict[str, str] = {
            "Content-Type": "application/json",
            "Accept": "text/event-stream",
        }
        if self.api_key:
            self.headers["x-api-key"] = self.api_key

    def _build_payload(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """Constructs the LangGraph /runs/stream payload."""
        user_content = inputs.get("query") or inputs.get("input") or inputs.get("prompt") or ""
        return {
            "assistant_id": self.assistant_id,
            "input": {"messages": [{"role": "user", "content": user_content}]},
            "stream_mode": [self.stream_mode],
        }

    def execute(self, inputs: Dict[str, Any]) -> TargetResult:
        """Executes LangGraph streaming request, accumulating text and trajectory spans."""
        t0 = time.perf_counter()
        trace_id = f"tr-lg-{uuid.uuid4().hex[:12]}"
        root_span_id = f"root-{uuid.uuid4().hex[:8]}"

        spans: List[Span] = []
        output_chunks: List[str] = []
        node_sequence: List[str] = []
        tokens_in: Optional[int] = None
        tokens_out: Optional[int] = None
        status = TargetStatus.SUCCESS
        error_msg: Optional[str] = None

        root_start = datetime.now(timezone.utc)
        payload = self._build_payload(inputs)
        data = json.dumps(payload).encode("utf-8")

        req = urllib.request.Request(
            self.url,
            data=data,
            headers=self.headers,
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=self.timeout_seconds) as resp:
                if resp.status != 200:
                    return TargetResult(
                        target_id=self.target_id,
                        status=TargetStatus.FAILED,
                        error_code=str(resp.status),
                        error_message=f"HTTP {resp.status} from LangGraph server",
                        trace_id=trace_id,
                    )

                # Process Server-Sent Events (SSE) stream
                current_event = "message"
                for line_bytes in resp:
                    line = line_bytes.decode("utf-8", "replace").strip()
                    if not line:
                        continue

                    if line.startswith("event:"):
                        current_event = line[len("event:") :].strip()
                        continue

                    if line.startswith("data:"):
                        raw_data = line[len("data:") :].strip()
                        if not raw_data or raw_data == "[DONE]":
                            continue

                        try:
                            parsed = json.loads(raw_data)
                        except json.JSONDecodeError:
                            parsed = raw_data

                        span = self._process_sse_event(
                            event_type=current_event,
                            data=parsed,
                            trace_id=trace_id,
                            parent_span_id=root_span_id,
                            output_chunks=output_chunks,
                            node_sequence=node_sequence,
                        )
                        if span:
                            spans.append(span)

        except urllib.error.HTTPError as e:
            status = TargetStatus.FAILED
            error_msg = f"HTTP {e.code}: {e.reason}"
        except (urllib.error.URLError, TimeoutError, socket.timeout) as e:
            status = TargetStatus.TIMEOUT
            error_msg = str(e)
        except Exception as e:
            status = TargetStatus.FAILED
            error_msg = f"LangGraph execution failed: {e}"

        latency_ms = (time.perf_counter() - t0) * 1000.0
        root_end = datetime.now(timezone.utc)

        # Root Agent Span
        root_span = Span(
            trace_id=trace_id,
            span_id=root_span_id,
            parent_span_id=None,
            name=self.name,
            kind=SpanKind.AGENT,
            status=SpanStatus.OK if status == TargetStatus.SUCCESS else SpanStatus.ERROR,
            start_time=root_start,
            end_time=root_end,
            duration_ms=latency_ms,
            attributes={
                "assistant_id": self.assistant_id,
                "node_sequence": node_sequence,
                "stream_mode": self.stream_mode,
            },
            error=error_msg,
            source="langgraph_streaming",
        )
        all_spans = [root_span] + spans

        final_text = "".join(output_chunks).strip() if output_chunks else None

        # Calculate estimated cost if pricing given
        cost_usd = None
        cost_basis = CostBasis.UNAVAILABLE
        if self.pricing and (tokens_in is not None or tokens_out is not None):
            cost_usd = self.pricing.calculate_cost(tokens_in, tokens_out)
            if cost_usd is not None:
                cost_basis = CostBasis.ESTIMATED

        return TargetResult(
            target_id=self.target_id,
            status=status,
            output_text=final_text,
            latency_ms=latency_ms,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            cost_usd=cost_usd,
            cost_basis=cost_basis,
            error_message=error_msg,
            trace_id=trace_id,
            trajectory=all_spans,
            metadata={
                "node_sequence": node_sequence,
                "total_transitions": len(node_sequence),
                "assistant_id": self.assistant_id,
            },
        )

    def stream(self, inputs: Dict[str, Any]) -> Iterator[TargetChunk]:
        """Yields streaming chunks in real time as tokens and node transitions arrive."""
        payload = self._build_payload(inputs)
        data = json.dumps(payload).encode("utf-8")

        req = urllib.request.Request(
            self.url,
            data=data,
            headers=self.headers,
            method="POST",
        )

        with urllib.request.urlopen(req, timeout=self.timeout_seconds) as resp:
            current_event = "message"
            for line_bytes in resp:
                line = line_bytes.decode("utf-8", "replace").strip()
                if not line:
                    continue

                if line.startswith("event:"):
                    current_event = line[len("event:") :].strip()
                    continue

                if line.startswith("data:"):
                    raw_data = line[len("data:") :].strip()
                    if raw_data == "[DONE]":
                        yield TargetChunk(target_id=self.target_id, delta_text="", is_final=True)
                        break

                    try:
                        parsed = json.loads(raw_data)
                    except json.JSONDecodeError:
                        parsed = raw_data

                    delta = self._extract_delta(current_event, parsed)
                    if delta:
                        yield TargetChunk(
                            target_id=self.target_id,
                            delta_text=delta,
                            is_final=False,
                            metadata={"event": current_event},
                        )

    def _process_sse_event(
        self,
        event_type: str,
        data: Any,
        trace_id: str,
        parent_span_id: str,
        output_chunks: List[str],
        node_sequence: List[str],
    ) -> Optional[Span]:
        """Maps an individual LangGraph SSE event into a canonical Span and updates output text."""
        now = datetime.now(timezone.utc)

        # 1. Updates event: {node_name: {messages: ..., state: ...}}
        if event_type == "updates" and isinstance(data, dict):
            for node_name, node_output in data.items():
                node_sequence.append(str(node_name))
                kind = SpanKind.TOOL if "tool" in str(node_name).lower() else SpanKind.WORKFLOW_STEP

                # Extract messages if present
                if isinstance(node_output, dict) and "messages" in node_output:
                    msgs = node_output["messages"]
                    if isinstance(msgs, list) and msgs:
                        last_msg = msgs[-1]
                        if isinstance(last_msg, dict) and "content" in last_msg:
                            content = str(last_msg["content"])
                            if content:
                                output_chunks.append(content)

                return Span(
                    trace_id=trace_id,
                    span_id=f"node-{node_name}-{uuid.uuid4().hex[:6]}",
                    parent_span_id=parent_span_id,
                    name=str(node_name),
                    kind=kind,
                    status=SpanStatus.OK,
                    start_time=now,
                    end_time=now,
                    duration_ms=0.0,
                    attributes=scrub_secrets(
                        node_output if isinstance(node_output, dict) else {"output": node_output}
                    ),
                    source="langgraph_streaming",
                )

        # 2. Values event: current graph state snapshot
        elif event_type == "values" and isinstance(data, dict):
            if "messages" in data and isinstance(data["messages"], list) and data["messages"]:
                last_msg = data["messages"][-1]
                if isinstance(last_msg, dict) and "content" in last_msg:
                    content = str(last_msg["content"])
                    if content and not output_chunks:
                        output_chunks.append(content)

        # 3. Messages event: streaming tokens
        elif event_type in ("messages", "messages/partial"):
            delta = self._extract_delta(event_type, data)
            if delta:
                output_chunks.append(delta)

        # 4. LangChain event callback streaming
        elif event_type == "events" and isinstance(data, dict):
            event_name = data.get("event")
            if event_name == "on_tool_start":
                return Span(
                    trace_id=trace_id,
                    span_id=f"tool-{uuid.uuid4().hex[:6]}",
                    parent_span_id=parent_span_id,
                    name=data.get("name", "tool"),
                    kind=SpanKind.TOOL,
                    status=SpanStatus.OK,
                    start_time=now,
                    attributes=scrub_secrets(data.get("data", {})),
                    source="langgraph_event",
                )
            elif event_name == "on_chat_model_end":
                usage = data.get("data", {}).get("output", {}).get("usage_metadata", {})
                return Span(
                    trace_id=trace_id,
                    span_id=f"llm-{uuid.uuid4().hex[:6]}",
                    parent_span_id=parent_span_id,
                    name=data.get("name", "chat_model"),
                    kind=SpanKind.LLM,
                    status=SpanStatus.OK,
                    start_time=now,
                    end_time=now,
                    prompt_tokens=usage.get("input_tokens"),
                    completion_tokens=usage.get("output_tokens"),
                    total_tokens=usage.get("total_tokens"),
                    attributes=scrub_secrets(data.get("data", {})),
                    source="langgraph_event",
                )

        return None

    def _extract_delta(self, event_type: str, data: Any) -> Optional[str]:
        """Extracts text delta from diverse LangGraph SSE event formats."""
        if isinstance(data, str):
            return data
        if isinstance(data, list) and data:
            last = data[-1]
            if isinstance(last, dict):
                return last.get("content")
            return str(last)
        if isinstance(data, dict):
            if "content" in data:
                return str(data["content"])
            if "delta" in data and isinstance(data["delta"], dict):
                return data["delta"].get("content")
        return None


class RunportLangGraphTracer:
    """In-process callback tracer for LangGraph and LangChain workflows.

    Pass directly to graph invocations:
    >>> tracer = RunportLangGraphTracer(trace_id="my-trace")
    >>> result = graph.invoke({"messages": [HumanMessage("Hello")]}, config={"callbacks": [tracer]})
    >>> spans = tracer.get_spans()
    """

    def __init__(self, trace_id: Optional[str] = None, name: str = "LangGraphWorkflow") -> None:
        self.trace_id = trace_id or f"tr-lg-{uuid.uuid4().hex[:12]}"
        self.name = name
        self.active_spans: Dict[str, Dict[str, Any]] = {}
        self.finished_spans: List[Span] = []
        self.start_time = datetime.now(timezone.utc)
        self.end_time: Optional[datetime] = None

    def on_chain_start(
        self,
        serialized: Dict[str, Any],
        inputs: Dict[str, Any],
        *,
        run_id: Any,
        parent_run_id: Optional[Any] = None,
        **kwargs: Any,
    ) -> None:
        """Called when a graph node or chain starts execution."""
        sid = str(run_id)
        name = (serialized or {}).get("name") or kwargs.get("name") or "chain_step"
        now = datetime.now(timezone.utc)

        self.active_spans[sid] = {
            "name": name,
            "kind": SpanKind.TOOL if "tool" in name.lower() else SpanKind.WORKFLOW_STEP,
            "parent_id": str(parent_run_id) if parent_run_id else None,
            "start_time": now,
            "inputs": scrub_secrets(inputs),
        }

    def on_chain_end(
        self,
        outputs: Dict[str, Any],
        *,
        run_id: Any,
        parent_run_id: Optional[Any] = None,
        **kwargs: Any,
    ) -> None:
        """Called when a graph node or chain finishes execution."""
        sid = str(run_id)
        info = self.active_spans.pop(sid, None)
        if not info:
            return

        now = datetime.now(timezone.utc)
        delta_ms = max(0.0, (now - info["start_time"]).total_seconds() * 1000.0)

        attrs = {"inputs": info["inputs"], "outputs": scrub_secrets(outputs)}
        span = Span(
            trace_id=self.trace_id,
            span_id=sid,
            parent_span_id=info["parent_id"],
            name=info["name"],
            kind=info["kind"],
            status=SpanStatus.OK,
            start_time=info["start_time"],
            end_time=now,
            duration_ms=delta_ms,
            attributes=attrs,
            source="langgraph_tracer",
        )
        self.finished_spans.append(span)

    def on_chain_error(
        self,
        error: BaseException,
        *,
        run_id: Any,
        parent_run_id: Optional[Any] = None,
        **kwargs: Any,
    ) -> None:
        """Called when a graph node or chain fails."""
        sid = str(run_id)
        info = self.active_spans.pop(sid, None)
        if not info:
            return

        now = datetime.now(timezone.utc)
        delta_ms = max(0.0, (now - info["start_time"]).total_seconds() * 1000.0)

        span = Span(
            trace_id=self.trace_id,
            span_id=sid,
            parent_span_id=info["parent_id"],
            name=info["name"],
            kind=info["kind"],
            status=SpanStatus.ERROR,
            start_time=info["start_time"],
            end_time=now,
            duration_ms=delta_ms,
            error=scrub_secrets(str(error)),
            attributes={"inputs": info["inputs"]},
            source="langgraph_tracer",
        )
        self.finished_spans.append(span)

    def on_tool_start(
        self,
        serialized: Dict[str, Any],
        input_str: str,
        *,
        run_id: Any,
        parent_run_id: Optional[Any] = None,
        **kwargs: Any,
    ) -> None:
        """Called when a tool execution starts."""
        sid = str(run_id)
        name = (serialized or {}).get("name") or kwargs.get("name") or "tool"
        now = datetime.now(timezone.utc)

        self.active_spans[sid] = {
            "name": name,
            "kind": SpanKind.TOOL,
            "parent_id": str(parent_run_id) if parent_run_id else None,
            "start_time": now,
            "input": scrub_secrets(input_str),
        }

    def on_tool_end(
        self,
        output: str,
        *,
        run_id: Any,
        parent_run_id: Optional[Any] = None,
        **kwargs: Any,
    ) -> None:
        """Called when a tool execution finishes."""
        sid = str(run_id)
        info = self.active_spans.pop(sid, None)
        if not info:
            return

        now = datetime.now(timezone.utc)
        delta_ms = max(0.0, (now - info["start_time"]).total_seconds() * 1000.0)

        span = Span(
            trace_id=self.trace_id,
            span_id=sid,
            parent_span_id=info["parent_id"],
            name=info["name"],
            kind=SpanKind.TOOL,
            status=SpanStatus.OK,
            start_time=info["start_time"],
            end_time=now,
            duration_ms=delta_ms,
            attributes={"input": info.get("input"), "output": scrub_secrets(output)},
            source="langgraph_tracer",
        )
        self.finished_spans.append(span)

    def on_llm_start(
        self,
        serialized: Dict[str, Any],
        prompts: List[str],
        *,
        run_id: Any,
        parent_run_id: Optional[Any] = None,
        **kwargs: Any,
    ) -> None:
        """Called when an LLM call starts."""
        sid = str(run_id)
        name = (serialized or {}).get("name") or kwargs.get("name") or "llm"
        now = datetime.now(timezone.utc)

        self.active_spans[sid] = {
            "name": name,
            "kind": SpanKind.LLM,
            "parent_id": str(parent_run_id) if parent_run_id else None,
            "start_time": now,
            "model": (serialized or {}).get("model") or kwargs.get("model"),
            "prompts": scrub_secrets(prompts),
        }

    def on_llm_end(
        self,
        response: Any,
        *,
        run_id: Any,
        parent_run_id: Optional[Any] = None,
        **kwargs: Any,
    ) -> None:
        """Called when an LLM call finishes."""
        sid = str(run_id)
        info = self.active_spans.pop(sid, None)
        if not info:
            return

        now = datetime.now(timezone.utc)
        delta_ms = max(0.0, (now - info["start_time"]).total_seconds() * 1000.0)

        # Extract tokens from LLM response
        tokens_in = None
        tokens_out = None
        total_tokens = None
        llm_output = getattr(response, "llm_output", None) or {}
        if isinstance(llm_output, dict):
            usage = llm_output.get("token_usage", {})
            if isinstance(usage, dict):
                tokens_in = usage.get("prompt_tokens")
                tokens_out = usage.get("completion_tokens")
                total_tokens = usage.get("total_tokens")

        span = Span(
            trace_id=self.trace_id,
            span_id=sid,
            parent_span_id=info["parent_id"],
            name=info["name"],
            kind=SpanKind.LLM,
            status=SpanStatus.OK,
            start_time=info["start_time"],
            end_time=now,
            duration_ms=delta_ms,
            model=info.get("model"),
            prompt_tokens=tokens_in,
            completion_tokens=tokens_out,
            total_tokens=total_tokens,
            attributes={"prompts": info.get("prompts")},
            source="langgraph_tracer",
        )
        self.finished_spans.append(span)

    def get_spans(self) -> List[Span]:
        """Returns ordered list of all completed spans."""
        return list(self.finished_spans)

    def get_trace(self) -> Trace:
        """Constructs a canonical Trace encompassing all spans recorded by this tracer."""
        now = datetime.now(timezone.utc)
        status = SpanStatus.OK
        if any(s.status == SpanStatus.ERROR for s in self.finished_spans):
            status = SpanStatus.ERROR

        # Enforce valid parent references
        spans = list(self.finished_spans)
        valid_ids = {s.span_id for s in spans}
        for s in spans:
            if s.parent_span_id and s.parent_span_id not in valid_ids:
                s.parent_span_id = None

        return Trace(
            trace_id=self.trace_id,
            name=self.name,
            status=status,
            start_time=self.start_time,
            end_time=now,
            spans=spans,
            source="langgraph_tracer",
        )

"""Dify API connector for blocking and streaming chat-messages endpoints.

Only `urllib.request.urlopen` touches the network, so tests replace it.
Keys are used in authorization headers only and never returned in results or logged.
"""

from __future__ import annotations

import json
import re
import socket
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

KEPT_HEADERS = ("retry-after", "x-ratelimit-remaining", "x-ratelimit-limit", "x-ratelimit-reset", "content-length", "content-type")
_DIFY_KEY_PATTERN = re.compile(r"app-[A-Za-z0-9]{8,}")


def scrub_dify_secrets(text: str) -> str:
    """Removes Dify app keys and Bearer tokens from text destined for logs or reports."""
    text = _DIFY_KEY_PATTERN.sub("[REDACTED_DIFY_KEY]", text)
    return re.sub(r"(Bearer\s+)\S+", r"\1[REDACTED_SECRET]", text, flags=re.IGNORECASE)


def post_chat_message(url: str, api_key: str, payload: Dict[str, Any], timeout_s: float) -> Dict[str, Any]:
    """Execute one blocking Dify Chat Messages call.

    Returns:
        {outcome, http_status, body_text, wall_ms, client_start_utc, headers, response_bytes, request_bytes}.
        outcome: HTTP, CONNECTION_ERROR, AMBIGUOUS_TIMEOUT.
    """
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        method="POST",
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
    )
    start_utc = datetime.now(timezone.utc).isoformat()
    t0 = time.perf_counter()
    base = {
        "client_start_utc": start_utc,
        "request_bytes": len(data),
        "headers": {},
        "http_status": None,
        "body_text": "",
        "response_bytes": 0,
    }
    try:
        with urllib.request.urlopen(req, timeout=timeout_s) as resp:
            body = resp.read()
            wall = (time.perf_counter() - t0) * 1000
            return {
                **base,
                "outcome": "HTTP",
                "http_status": resp.status,
                "body_text": scrub_dify_secrets(body.decode("utf-8", "replace")),
                "wall_ms": wall,
                "response_bytes": len(body),
                "headers": {k: v for k, v in dict(resp.headers).items() if k.lower() in KEPT_HEADERS},
            }
    except urllib.error.HTTPError as e:
        body = e.read() if hasattr(e, "read") else b""
        wall = (time.perf_counter() - t0) * 1000
        return {
            **base,
            "outcome": "HTTP",
            "http_status": e.code,
            "body_text": scrub_dify_secrets(body.decode("utf-8", "replace")),
            "wall_ms": wall,
            "response_bytes": len(body),
            "headers": {k: v for k, v in dict(e.headers).items() if k.lower() in KEPT_HEADERS},
        }
    except (socket.timeout, TimeoutError):
        return {**base, "outcome": "AMBIGUOUS_TIMEOUT", "wall_ms": (time.perf_counter() - t0) * 1000}
    except urllib.error.URLError as e:
        if isinstance(getattr(e, "reason", None), (socket.timeout, TimeoutError)):
            return {**base, "outcome": "AMBIGUOUS_TIMEOUT", "wall_ms": (time.perf_counter() - t0) * 1000}
        return {
            **base,
            "outcome": "CONNECTION_ERROR",
            "wall_ms": (time.perf_counter() - t0) * 1000,
            "body_text": scrub_dify_secrets(str(e.reason)),
        }


def post_chat_stream(
    url: str,
    api_key: str,
    payload: Dict[str, Any],
    timeout_s: float,
    max_total_s: float = 600.0,
) -> Dict[str, Any]:
    """Execute one streaming Dify Chat Messages call consuming Server-Sent Events (SSE).

    Returns:
        {outcome, http_status, events, wall_ms, client_start_utc, request_bytes, response_bytes, malformed_lines, body_text}.
    """
    data = json.dumps({**payload, "response_mode": "streaming"}).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        method="POST",
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
    )
    start_utc = datetime.now(timezone.utc).isoformat()
    t0 = time.perf_counter()
    events: List[Tuple[float, Dict[str, Any]]] = []
    base = {
        "client_start_utc": start_utc,
        "request_bytes": len(data),
        "http_status": None,
        "events": events,
        "response_bytes": 0,
        "malformed_lines": 0,
        "body_text": "",
    }

    def ms() -> float:
        return (time.perf_counter() - t0) * 1000

    try:
        with urllib.request.urlopen(req, timeout=timeout_s) as resp:
            status = resp.status
            size = malformed = 0
            if status != 200:
                body = resp.read()
                return {
                    **base,
                    "outcome": "HTTP",
                    "http_status": status,
                    "wall_ms": ms(),
                    "response_bytes": len(body),
                    "body_text": scrub_dify_secrets(body.decode("utf-8", "replace")),
                }
            for raw in resp:
                size += len(raw)
                if ms() / 1000.0 > max_total_s:
                    return {
                        **base,
                        "outcome": "AMBIGUOUS_TIMEOUT",
                        "http_status": status,
                        "wall_ms": ms(),
                        "response_bytes": size,
                        "malformed_lines": malformed,
                    }
                line = raw.strip()
                if not line.startswith(b"data:"):
                    continue
                try:
                    ev = json.loads(line[5:].strip())
                except ValueError:
                    malformed += 1
                    continue
                if isinstance(ev, dict):
                    events.append((ms(), ev))
            return {
                **base,
                "outcome": "HTTP",
                "http_status": status,
                "wall_ms": ms(),
                "response_bytes": size,
                "malformed_lines": malformed,
            }
    except urllib.error.HTTPError as e:
        body = e.read() if hasattr(e, "read") else b""
        return {
            **base,
            "outcome": "HTTP",
            "http_status": e.code,
            "wall_ms": ms(),
            "response_bytes": len(body),
            "body_text": scrub_dify_secrets(body.decode("utf-8", "replace")),
        }
    except (socket.timeout, TimeoutError):
        return {**base, "outcome": "AMBIGUOUS_TIMEOUT", "wall_ms": ms()}
    except urllib.error.URLError as e:
        if isinstance(getattr(e, "reason", None), (socket.timeout, TimeoutError)):
            return {**base, "outcome": "AMBIGUOUS_TIMEOUT", "wall_ms": ms()}
        return {
            **base,
            "outcome": "CONNECTION_ERROR",
            "wall_ms": ms(),
            "body_text": scrub_dify_secrets(str(e.reason)),
        }


from runport.core.security import validate_safe_url
from runport.providers.base import scrub_secrets
from runport.targets.base import (
    BillingMode,
    CostBasis,
    Target,
    TargetPricing,
    TargetResult,
    TargetStatus,
    TargetType,
    billing_for_url,
)
from runport.traces.domain import Span, SpanKind, SpanStatus


def _build_dify_node_spans(node_list: List[Dict[str, Any]]) -> List[Span]:
    import uuid

    spans: List[Span] = []
    for idx, node in enumerate(node_list):
        if not isinstance(node, dict):
            continue
        node_id = str(node.get("node_id") or node.get("id") or f"node-{idx}")
        title = str(node.get("title") or node.get("node_type") or node_id)
        raw_type = str(node.get("node_type") or "").lower()

        if raw_type in ("llm", "llm-node"):
            kind = SpanKind.LLM
        elif raw_type in ("knowledge-retrieval", "retrieval"):
            kind = SpanKind.RETRIEVAL
        elif raw_type in ("tool", "api_tool"):
            kind = SpanKind.TOOL
        elif raw_type in ("agent", "agent-node"):
            kind = SpanKind.AGENT
        else:
            kind = SpanKind.WORKFLOW_STEP

        raw_status = str(node.get("status") or "").lower()
        if raw_status in ("succeeded", "success"):
            status = SpanStatus.OK
        elif raw_status in ("failed", "error"):
            status = SpanStatus.ERROR
        elif raw_status in ("stopped", "cancelled"):
            status = SpanStatus.CANCELLED
        else:
            status = SpanStatus.UNSET

        elapsed = node.get("elapsed_time")
        duration_ms = None
        if elapsed is not None:
            try:
                val = float(elapsed)
                duration_ms = round(val * 1000.0 if val < 500.0 else val, 3)
            except (ValueError, TypeError):
                duration_ms = None

        exec_meta = node.get("execution_metadata") or {}
        p_tokens = exec_meta.get("prompt_tokens")
        c_tokens = exec_meta.get("completion_tokens")
        t_tokens = exec_meta.get("total_tokens")

        attrs: Dict[str, Any] = {
            "node_id": node_id,
            "node_type": raw_type,
        }
        if "inputs" in node:
            attrs["inputs"] = node["inputs"]
        if "outputs" in node:
            attrs["outputs"] = node["outputs"]

        span = Span(
            trace_id="pending",
            span_id=f"sp-dify-{uuid.uuid4().hex[:10]}",
            parent_span_id=None,
            name=title,
            kind=kind,
            status=status,
            duration_ms=duration_ms,
            prompt_tokens=p_tokens,
            completion_tokens=c_tokens,
            total_tokens=t_tokens,
            attributes=scrub_secrets(attrs),
            error=scrub_secrets(str(node.get("error"))) if node.get("error") else None,
        )
        spans.append(span)
    return spans


class DifyConnector(Target):
    """Benchmarks Dify Chat Applications and Workflow Applications.

    Supports both blocking and streaming modes for:
    - Chat Apps: POST /v1/chat-messages
    - Workflow Apps: POST /v1/workflows/run
    """

    def __init__(
        self,
        target_id: str,
        name: str,
        api_key: str,
        base_url: str = "https://api.dify.ai/v1",
        app_type: str = "chat",  # 'chat' or 'workflow'
        response_mode: str = "blocking",  # 'blocking' or 'streaming'
        user: str = "runport-benchmark",
        conversation_id: Optional[str] = None,
        pricing: Optional[TargetPricing] = None,
        timeout_seconds: float = 30.0,
        max_retries: int = 3,
        allow_localhost: bool = False,
        host_allowlist: Optional[List[str]] = None,
        billing: Optional[BillingMode] = None,
    ) -> None:
        safe_url = validate_safe_url(
            base_url,
            allow_localhost=allow_localhost,
            host_allowlist=host_allowlist,
        )
        caps = ["streaming", "usage"]
        if app_type.lower() == "workflow":
            caps.append("per_step_trace")

        super().__init__(
            target_id=target_id,
            name=name,
            target_type=TargetType.WORKFLOW_DIFY,
            capabilities=caps,
            pricing=pricing,
            timeout_seconds=timeout_seconds,
            max_retries=max_retries,
        )
        self.api_key = api_key
        self.base_url = safe_url.rstrip("/")
        self.billing = billing_for_url(self.base_url, billing)
        self.app_type = app_type.lower()
        self.response_mode = response_mode.lower()
        self.user = user
        self.conversation_id = conversation_id

    def execute(
        self,
        input_payload: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None,
    ) -> TargetResult:
        if self.app_type == "workflow":
            url = f"{self.base_url}/workflows/run"
            inputs = input_payload.get("inputs")
            if inputs is None:
                inputs = {k: v for k, v in input_payload.items() if k not in ("user", "conversation_id")}
            req_payload: Dict[str, Any] = {
                "inputs": inputs,
                "response_mode": self.response_mode,
                "user": input_payload.get("user") or self.user,
            }
        else:
            url = f"{self.base_url}/chat-messages"
            inputs = input_payload.get("inputs", {})
            query = str(input_payload.get("query") or input_payload.get("input") or "")
            req_payload = {
                "inputs": inputs,
                "query": query,
                "response_mode": self.response_mode,
                "user": input_payload.get("user") or self.user,
            }
            conv_id = input_payload.get("conversation_id") or self.conversation_id
            if conv_id:
                req_payload["conversation_id"] = conv_id

        if self.response_mode == "streaming":
            res = post_chat_stream(
                url=url,
                api_key=self.api_key,
                payload=req_payload,
                timeout_s=self.timeout_seconds,
            )
        else:
            res = post_chat_message(
                url=url,
                api_key=self.api_key,
                payload=req_payload,
                timeout_s=self.timeout_seconds,
            )

        outcome = res.get("outcome")
        http_status = res.get("http_status")
        wall_ms = res.get("wall_ms", 0.0)

        if outcome == "AMBIGUOUS_TIMEOUT":
            return TargetResult(
                target_id=self.target_id,
                status=TargetStatus.TIMEOUT,
                latency_ms=wall_ms,
                error_message="Request timed out",
            )
        if outcome == "CONNECTION_ERROR":
            return TargetResult(
                target_id=self.target_id,
                status=TargetStatus.FAILED,
                latency_ms=wall_ms,
                error_message=res.get("body_text", "Connection error"),
            )

        if http_status == 429:
            return TargetResult(
                target_id=self.target_id,
                status=TargetStatus.RATE_LIMITED,
                latency_ms=wall_ms,
                error_code="429",
                error_message="Dify rate limit exceeded",
            )
        if http_status in (401, 403):
            return TargetResult(
                target_id=self.target_id,
                status=TargetStatus.UNAUTHORIZED,
                latency_ms=wall_ms,
                error_code=str(http_status),
                error_message="Unauthorized Dify API key",
            )
        if http_status != 200:
            return TargetResult(
                target_id=self.target_id,
                status=TargetStatus.FAILED,
                latency_ms=wall_ms,
                error_code=str(http_status),
                error_message=res.get("body_text", f"HTTP {http_status}"),
            )

        # Parse 200 OK responses
        output_text = None
        tokens_in = None
        tokens_out = None
        metadata: Dict[str, Any] = {}

        if self.response_mode == "streaming":
            events = res.get("events", [])
            text_chunks = []
            per_node_data = []
            for _, ev in events:
                ev_type = ev.get("event")
                if ev_type == "message":
                    text_chunks.append(ev.get("answer", ""))
                elif ev_type == "message_end":
                    usage = ev.get("metadata", {}).get("usage", {})
                    tokens_in = usage.get("prompt_tokens")
                    tokens_out = usage.get("completion_tokens")
                elif ev_type == "node_finished":
                    per_node_data.append(ev.get("data", {}))
                elif ev_type == "workflow_finished":
                    outputs = ev.get("data", {}).get("outputs", {})
                    if outputs:
                        output_text = outputs.get("result") or outputs.get("output") or json.dumps(outputs)
                    usage = ev.get("data", {})
                    tokens_out = usage.get("total_tokens")

            if text_chunks and output_text is None:
                output_text = "".join(text_chunks)
            if per_node_data:
                metadata["per_node_data"] = per_node_data
        else:
            try:
                body = json.loads(res.get("body_text", "{}"))
            except Exception:
                return TargetResult(
                    target_id=self.target_id,
                    status=TargetStatus.INVALID_OUTPUT,
                    latency_ms=wall_ms,
                    error_message="Malformed non-JSON response from Dify",
                )

            if self.app_type == "workflow":
                data = body.get("data", {})
                outputs = data.get("outputs", {})
                if isinstance(outputs, dict):
                    output_text = outputs.get("result") or outputs.get("output") or json.dumps(outputs)
                else:
                    output_text = str(outputs) if outputs else None
                tokens_out = data.get("total_tokens")
                metadata["workflow_run_id"] = data.get("id")
                metadata["total_steps"] = data.get("total_steps")
                if "node_executions" in data:
                    metadata["per_node_data"] = data.get("node_executions")
            else:
                output_text = body.get("answer")
                usage = body.get("metadata", {}).get("usage", {})
                tokens_in = usage.get("prompt_tokens")
                tokens_out = usage.get("completion_tokens")
                metadata["conversation_id"] = body.get("conversation_id")
                metadata["message_id"] = body.get("message_id")

        cost_usd = None
        cost_basis = CostBasis.UNAVAILABLE
        if self.pricing:
            cost_usd = self.pricing.calculate_cost(tokens_in, tokens_out)
            if cost_usd is not None:
                cost_basis = CostBasis.ESTIMATED

        trajectory = None
        node_records = metadata.get("per_node_data")
        if node_records and isinstance(node_records, list):
            trajectory = _build_dify_node_spans(node_records)

        return TargetResult(
            target_id=self.target_id,
            status=TargetStatus.SUCCESS if output_text is not None else TargetStatus.INVALID_OUTPUT,
            output_text=output_text,
            latency_ms=wall_ms,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            cost_usd=cost_usd,
            cost_basis=cost_basis,
            metadata=metadata,
            trajectory=trajectory,
        )

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
from typing import Any, Dict, List, Tuple

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

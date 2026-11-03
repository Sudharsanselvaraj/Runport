"""Local Ollama connector for Runport benchmarks.

Executes evaluations against local or private Ollama instances running on localhost.
Cost basis is strictly UNAVAILABLE ($0.00) representing zero-cost local compute.
"""

import json
import time
import urllib.error
import urllib.request
from typing import Any, Dict, List, Optional

from runport.core.security import validate_safe_url
from runport.providers.base import scrub_secrets
from runport.targets.base import (
    CostBasis,
    Target,
    TargetPricing,
    TargetResult,
    TargetStatus,
    TargetType,
)


class OllamaConnector(Target):
    """Benchmarks local Ollama models (/api/chat and /api/generate)."""

    def __init__(
        self,
        target_id: str,
        name: str,
        model: str,
        base_url: str = "http://127.0.0.1:11434",
        system_prompt: Optional[str] = None,
        format: Optional[str] = None,  # "json" or None
        options: Optional[Dict[str, Any]] = None,
        timeout_seconds: float = 60.0,
        allow_localhost: bool = True,
        host_allowlist: Optional[List[str]] = None,
    ) -> None:
        safe_url = validate_safe_url(
            base_url,
            allow_localhost=allow_localhost,
            host_allowlist=host_allowlist,
        )
        super().__init__(
            target_id=target_id,
            name=name,
            target_type=TargetType.RAW_MODEL,
            capabilities=["streaming", "structured_output", "usage"],
            pricing=None,  # Free / local compute
            timeout_seconds=timeout_seconds,
            max_retries=1,
        )
        self.model = model
        self.base_url = safe_url.rstrip("/")
        self.system_prompt = system_prompt
        self.format = format
        self.options = options or {}

    def execute(
        self,
        input_payload: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None,
    ) -> TargetResult:
        messages = input_payload.get("messages")
        if not messages:
            query = str(input_payload.get("query") or input_payload.get("input") or "")
            messages = []
            sys_msg = input_payload.get("system_prompt") or self.system_prompt
            if sys_msg:
                messages.append({"role": "system", "content": str(sys_msg)})
            messages.append({"role": "user", "content": query})

        body: Dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "options": {**self.options, **input_payload.get("options", {})},
        }
        fmt = input_payload.get("format") or self.format
        if fmt:
            body["format"] = fmt

        url = f"{self.base_url}/api/chat"
        data = json.dumps(body).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        t0 = time.perf_counter()
        try:
            with urllib.request.urlopen(req, timeout=self.timeout_seconds) as resp:
                elapsed_ms = (time.perf_counter() - t0) * 1000.0
                raw = json.loads(resp.read().decode("utf-8", errors="replace"))

                msg = raw.get("message", {})
                output_text = msg.get("content")

                tokens_in = raw.get("prompt_eval_count")
                tokens_out = raw.get("eval_count")

                # If Ollama reported exact duration in nanoseconds
                total_duration_ns = raw.get("total_duration")
                if total_duration_ns:
                    elapsed_ms = total_duration_ns / 1_000_000.0

                return TargetResult(
                    target_id=self.target_id,
                    status=TargetStatus.SUCCESS if output_text is not None else TargetStatus.INVALID_OUTPUT,
                    output_text=output_text,
                    raw_output=scrub_secrets(raw),
                    latency_ms=elapsed_ms,
                    tokens_in=tokens_in,
                    tokens_out=tokens_out,
                    cost_usd=None,  # Null is not 0 for missing price; cost_basis indicates local/free
                    cost_basis=CostBasis.UNAVAILABLE,
                    provenance="LIVE",
                    metadata={
                        "model": raw.get("model", self.model),
                        "eval_duration_ms": (raw.get("eval_duration") or 0) / 1_000_000.0,
                    },
                )
        except urllib.error.HTTPError as e:
            elapsed_ms = (time.perf_counter() - t0) * 1000.0
            return TargetResult(
                target_id=self.target_id,
                status=TargetStatus.FAILED,
                latency_ms=elapsed_ms,
                error_code=str(e.code),
                error_message=scrub_secrets(str(e)),
            )
        except (urllib.error.URLError, TimeoutError) as e:
            elapsed_ms = (time.perf_counter() - t0) * 1000.0
            is_timeout = "timed out" in str(e).lower() or isinstance(e, TimeoutError)
            return TargetResult(
                target_id=self.target_id,
                status=TargetStatus.TIMEOUT if is_timeout else TargetStatus.FAILED,
                latency_ms=elapsed_ms,
                error_message=scrub_secrets(str(e)),
            )
        except Exception as e:
            elapsed_ms = (time.perf_counter() - t0) * 1000.0
            return TargetResult(
                target_id=self.target_id,
                status=TargetStatus.FAILED,
                latency_ms=elapsed_ms,
                error_message=scrub_secrets(str(e)),
            )

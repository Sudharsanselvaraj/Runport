"""OpenAI-compatible chat completions connector for Runport.

Supports OpenAI, OpenRouter, vLLM, Ollama, LocalAI, and any OpenAI-compatible provider.
"""

import json
import time
import urllib.error
from typing import Any, Dict, List, Optional

from runport.core.security import validate_safe_url
from runport.providers.base import ProviderError, RateLimitError, scrub_secrets
from runport.providers.http import RetryingPoster
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


class OpenAICompatConnector(Target):
    """Benchmarks OpenAI-compatible completions endpoints."""

    def __init__(
        self,
        target_id: str,
        name: str,
        model: str,
        base_url: str = "https://api.openai.com/v1",
        api_key: Optional[str] = None,
        custom_headers: Optional[Dict[str, str]] = None,
        default_params: Optional[Dict[str, Any]] = None,
        pricing: Optional[TargetPricing] = None,
        timeout_seconds: float = 30.0,
        max_retries: int = 3,
        allow_localhost: bool = False,
        allow_private: bool = False,
        host_allowlist: Optional[List[str]] = None,
        billing: Optional[BillingMode] = None,
    ) -> None:
        safe_url = validate_safe_url(
            base_url,
            allow_localhost=allow_localhost,
            allow_private=allow_private,
            host_allowlist=host_allowlist,
        )
        super().__init__(
            target_id=target_id,
            name=name,
            target_type=TargetType.RAW_MODEL,
            capabilities=["text", "usage", "response_format_passthrough"],  # see connectors/registry.py CONNECTOR_MATRIX
            pricing=pricing,
            timeout_seconds=timeout_seconds,
            max_retries=max_retries,
        )
        self.model = model
        self.base_url = safe_url.rstrip("/")
        self.billing = billing_for_url(self.base_url, billing)
        self.api_key = api_key
        self.custom_headers = custom_headers or {}
        self.default_params = default_params or {}
        self._poster = RetryingPoster(
            timeout_seconds=timeout_seconds,
            max_attempts=max_retries,
            backoff_base_seconds=0.01,
        )

    def execute(
        self,
        input_payload: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None,
    ) -> TargetResult:
        messages = input_payload.get("messages")
        if not messages and "query" in input_payload:
            system_prompt = input_payload.get("system_prompt")
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": str(input_payload["query"])})

        body = {
            "model": self.model,
            "messages": messages or [],
            **self.default_params,
        }

        # Override any specific parameters passed in input_payload
        for p in ("temperature", "max_tokens", "top_p", "response_format"):
            if p in input_payload:
                body[p] = input_payload[p]

        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            **self.custom_headers,
        }
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        url = f"{self.base_url}/chat/completions"
        start_time = time.perf_counter()

        try:
            post_res = self._poster.post(
                url=url,
                headers=headers,
                payload=body,
            )

            raw = json.loads(post_res.body.decode("utf-8", errors="replace"))
            choices = raw.get("choices", [])
            output_text = None
            if choices and isinstance(choices[0], dict):
                msg = choices[0].get("message", {})
                output_text = msg.get("content")

            usage = raw.get("usage", {})
            tokens_in = usage.get("prompt_tokens")
            tokens_out = usage.get("completion_tokens")

            cost_usd = None
            cost_basis = CostBasis.UNAVAILABLE
            if self.pricing:
                cost_usd = self.pricing.calculate_cost(tokens_in, tokens_out)
                if cost_usd is not None:
                    cost_basis = CostBasis.ESTIMATED

            return TargetResult(
                target_id=self.target_id,
                status=TargetStatus.SUCCESS if output_text is not None else TargetStatus.INVALID_OUTPUT,
                output_text=output_text,
                raw_output=scrub_secrets(raw),
                latency_ms=post_res.e2e_ms,
                tokens_in=tokens_in,
                tokens_out=tokens_out,
                cost_usd=cost_usd,
                cost_basis=cost_basis,
                metadata={
                    "model": raw.get("model", self.model),
                    "attempts": post_res.attempts,
                    "retry_errors": post_res.errors,
                },
            )
        except RateLimitError as e:
            elapsed_ms = (time.perf_counter() - start_time) * 1000.0
            return TargetResult(
                target_id=self.target_id,
                status=TargetStatus.RATE_LIMITED,
                latency_ms=elapsed_ms,
                error_code="429",
                error_message=str(e),
            )
        except ProviderError as e:
            elapsed_ms = (time.perf_counter() - start_time) * 1000.0
            is_to = any("TIMEOUT" in str(err) for err in (e.errors or [])) or "timeout" in str(e).lower()
            return TargetResult(
                target_id=self.target_id,
                status=TargetStatus.TIMEOUT if is_to else TargetStatus.FAILED,
                latency_ms=elapsed_ms,
                error_code="TIMEOUT" if is_to else (str(e.status) if e.status else None),
                error_message=str(e),
            )
        except Exception as e:
            elapsed_ms = (time.perf_counter() - start_time) * 1000.0
            is_timeout = "timed out" in str(e).lower() or isinstance(e, TimeoutError)
            return TargetResult(
                target_id=self.target_id,
                status=TargetStatus.TIMEOUT if is_timeout else TargetStatus.FAILED,
                latency_ms=elapsed_ms,
                error_message=scrub_secrets(str(e)),
            )

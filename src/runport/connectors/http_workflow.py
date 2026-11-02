"""Generic HTTP workflow connector for Runport.

Enables benchmarking of any custom HTTP REST endpoint, webhook, or workflow service.
Handles payload templating, output extraction, bounded retries, and secret scrubbing.
"""

import json
import time
from typing import Any, Dict, List, Optional

from runport.providers.base import ProviderError, RateLimitError, scrub_secrets
from runport.providers.http import RetryingPoster
from runport.targets.base import (
    CostBasis,
    Target,
    TargetPricing,
    TargetResult,
    TargetStatus,
    TargetType,
)


def _extract_nested_path(data: Any, path: str) -> Any:
    """Extracts a value from a nested dict/list using a dot-delimited path.
    
    Supports keys and integer list indices (e.g., 'choices.0.message.content').
    """
    if not path or not data:
        return data
    parts = path.split(".")
    current = data
    for p in parts:
        if isinstance(current, dict):
            current = current.get(p)
        elif isinstance(current, (list, tuple)):
            try:
                idx = int(p)
                current = current[idx]
            except (ValueError, IndexError):
                return None
        else:
            return None
    return current


class HttpWorkflowConnector(Target):
    """Benchmarks arbitrary HTTP endpoints transforming input JSON into output."""

    def __init__(
        self,
        target_id: str,
        name: str,
        url: str,
        method: str = "POST",
        headers: Optional[Dict[str, str]] = None,
        payload_template: Optional[Dict[str, Any]] = None,
        output_path: Optional[str] = None,
        pricing: Optional[TargetPricing] = None,
        timeout_seconds: float = 30.0,
        max_retries: int = 3,
    ) -> None:
        super().__init__(
            target_id=target_id,
            name=name,
            target_type=TargetType.WORKFLOW_HTTP,
            capabilities=["text", "json"],
            pricing=pricing,
            timeout_seconds=timeout_seconds,
            max_retries=max_retries,
        )
        self.url = url
        self.method = method.upper()
        self.headers = headers or {}
        self.payload_template = payload_template
        self.output_path = output_path
        self._poster = RetryingPoster(
            timeout_seconds=timeout_seconds,
            max_attempts=max_retries,
            backoff_base_seconds=0.01,  # Fast in tests
        )

    def _build_payload(self, input_payload: Dict[str, Any]) -> Dict[str, Any]:
        """Constructs the outbound payload from template or direct input."""
        if not self.payload_template:
            return input_payload
        
        # Deep copy template and substitute string variables
        payload_str = json.dumps(self.payload_template)
        for key, val in input_payload.items():
            if isinstance(val, (str, int, float, bool)):
                payload_str = payload_str.replace(f"{{{{{key}}}}}", str(val))
        try:
            return json.loads(payload_str)
        except json.JSONDecodeError:
            return {**self.payload_template, **input_payload}

    def execute(
        self,
        input_payload: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None,
    ) -> TargetResult:
        """Executes HTTP request, extracts result, and calculates metrics."""
        body_dict = self._build_payload(input_payload)
        
        req_headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            **self.headers,
        }

        start_time = time.perf_counter()
        try:
            post_res = self._poster.post(
                url=self.url,
                headers=req_headers,
                payload=body_dict,
            )

            raw_res = json.loads(post_res.body.decode("utf-8", errors="replace"))
            
            # Extract output text
            if self.output_path:
                extracted = _extract_nested_path(raw_res, self.output_path)
            elif isinstance(raw_res, dict):
                # Auto-detect common output keys
                for key in ("output", "answer", "text", "response", "result"):
                    if key in raw_res:
                        extracted = raw_res[key]
                        break
                else:
                    extracted = str(raw_res)
            else:
                extracted = str(raw_res)

            output_text = str(extracted) if extracted is not None else None

            # Token and cost accounting if reported in metadata
            usage = raw_res.get("usage", {}) if isinstance(raw_res, dict) else {}
            tokens_in = usage.get("prompt_tokens") or usage.get("input_tokens")
            tokens_out = usage.get("completion_tokens") or usage.get("output_tokens")
            
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
                raw_output=scrub_secrets(raw_res) if isinstance(raw_res, dict) else raw_res,
                latency_ms=post_res.e2e_ms,
                tokens_in=tokens_in,
                tokens_out=tokens_out,
                cost_usd=cost_usd,
                cost_basis=cost_basis,
                metadata={
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
            return TargetResult(
                target_id=self.target_id,
                status=TargetStatus.FAILED,
                latency_ms=elapsed_ms,
                error_code=str(e.status) if e.status else None,
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

"""OpenRouter as a Target, so catalog models run through the same guarded GenericRunner as every other target."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from runport.providers.base import ConfidentialityViolationError, LiveNotAuthorizedError, ProviderError, ProviderRequest, RateLimitError, scrub_secrets
from runport.providers.openrouter import OpenRouterAdapter
from runport.targets.base import BillingMode, CostBasis, Target, TargetPricing, TargetResult, TargetStatus, TargetType

DEFAULT_SYSTEM_PROMPT = "You are an AI benchmark evaluator. Answer accurately, ground all answers in academic guidelines, and never invent fees or policies."

_BASIS = {"PROVIDER_REPORTED": CostBasis.ACTUAL, "ESTIMATED_FROM_CATALOG": CostBasis.ESTIMATED}


class OpenRouterTarget(Target):
    """One OpenRouter model. Cost is ACTUAL when OpenRouter reports USD, ESTIMATED from catalog x reported tokens,
    and otherwise None: GenericRunner then books it UNRESOLVED (OpenRouter is always billable)."""

    provider_name = "openrouter"

    def __init__(
        self,
        model_id: str,
        adapter: Optional[OpenRouterAdapter] = None,
        system_prompt: Optional[str] = DEFAULT_SYSTEM_PROMPT,
        max_tokens: int = 512,
        timeout_seconds: float = 30.0,
        target_id: Optional[str] = None,
        temperature: Optional[float] = 0.0,
    ) -> None:
        super().__init__(
            target_id=target_id or model_id,
            name=target_id or model_id,
            target_type=TargetType.RAW_MODEL,
            capabilities=["text", "usage", "cost"],
            timeout_seconds=timeout_seconds,
            billing=BillingMode.BILLABLE,
        )
        self.model_id = model_id
        self.adapter = adapter or OpenRouterAdapter(timeout_seconds=timeout_seconds)
        self.system_prompt = system_prompt
        self.max_tokens = max_tokens
        self.temperature = temperature
        try:  # catalog price, when the model is registered; unknown models stay unpriced (and are refused before sending)
            in_price, out_price = self.adapter._get_pricing_for_model(model_id)
            self.pricing = TargetPricing(input_usd_per_1m=in_price, output_usd_per_1m=out_price)
        except Exception:
            self.pricing = None

    def execute(self, input_payload: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> TargetResult:
        query = input_payload.get("query") or input_payload.get("prompt") or input_payload.get("input")
        if not isinstance(query, str) or not query.strip():
            return TargetResult(self.target_id, TargetStatus.FAILED, error_code="NO_QUERY", error_message="case has no query text", request_sent=False)
        messages = ([{"role": "system", "content": self.system_prompt}] if self.system_prompt else []) + [{"role": "user", "content": query}]
        return self.generate_messages(messages, case_id=str(input_payload.get("id") or ""))

    def generate_messages(self, messages: List[Dict[str, str]], case_id: str = "") -> TargetResult:
        """One chat request with these messages, mapped to a TargetResult with cost provenance."""
        # GenericRunner has already enforced live authorization for this plan before any target is executed.
        request = ProviderRequest(
            model_id=self.model_id,
            messages=messages,
            max_tokens=self.max_tokens,
            temperature=self.temperature,
            live_authorized=True,
            case_id=case_id,
        )
        try:
            resp = self.adapter.generate(request)
        except (LiveNotAuthorizedError, ConfidentialityViolationError) as e:
            return TargetResult(self.target_id, TargetStatus.FAILED, error_code="REFUSED", error_message=scrub_secrets(str(e)), request_sent=False)
        except RateLimitError as e:
            return TargetResult(self.target_id, TargetStatus.RATE_LIMITED, error_code="429", error_message=scrub_secrets(str(e)))
        except ProviderError as e:
            sent = bool(e.attempts)  # pre-send refusals (no key, unknown price, registry blockers) carry no attempts
            status = TargetStatus.UNAUTHORIZED if e.status in (401, 403) else TargetStatus.TIMEOUT if "TIMEOUT" in (e.errors or []) else TargetStatus.FAILED
            return TargetResult(
                self.target_id,
                status,
                error_code=str(e.status) if e.status else ("PRE_SEND" if not sent else "PROVIDER_ERROR"),
                error_message=scrub_secrets(str(e)),
                request_sent=sent,
                metadata={"attempts": e.attempts, "errors": e.errors or []},
            )

        basis = _BASIS.get(resp.cost_basis)
        # resp.cost_usd is the adapter's recorded spend: actual when reported, else the catalog estimate; 0 only with UNAVAILABLE.
        cost = resp.cost_usd if basis is not None else None
        return TargetResult(
            target_id=self.target_id,
            status=TargetStatus.SUCCESS,
            output_text=resp.output_text,
            latency_ms=resp.latency_ms,
            tokens_in=resp.prompt_tokens,
            tokens_out=resp.completion_tokens,
            cost_usd=cost,
            cost_basis=basis or CostBasis.UNRESOLVED,
            provenance="LIVE",
            request_sent=True,
            metadata={
                "usage_source": resp.usage_source,
                "attempts": resp.attempts,
                "retry_errors": resp.retry_errors,
                "resolved_model_id": resp.resolved_model_id,
                "serving_provider": resp.serving_provider,
                "finish_reason": resp.finish_reason,
                "model_latency_ms": resp.model_latency_ms,
            },
        )

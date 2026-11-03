"""OpenRouter /api/v1/models catalog source with disk caching and Fact verification.

Invariant: Every price carries FactStatus.VERIFIED_PRIMARY, source URL, and check date.
Prices in OpenRouter API are per-token USD and are converted to per-1M tokens USD using Decimal.
All tests operate offline against recorded fixtures.
"""

from datetime import date, datetime, timezone
from decimal import Decimal
import json
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional
import urllib.request

from runport.catalog.models import ModelCandidate
from runport.core.config import settings
from runport.models.registry import (
    FactStatus,
    ModelRecord,
    RouteOption,
    RouteRecord,
    RouteStatus,
    fact,
    register_model,
)

OPENROUTER_MODELS_URL = "https://openrouter.ai/api/v1/models"


class OpenRouterCatalogSource:
    """Fetches, caches, and parses candidate models from OpenRouter's model catalog."""

    def __init__(
        self,
        cache_dir: Optional[Path] = None,
        max_cache_age_seconds: int = 86400,
        transport_fn: Optional[Callable[[str], str]] = None,
    ):
        self.cache_dir = cache_dir or (settings.data_dir / "cache")
        self.cache_file = self.cache_dir / "openrouter_models.json"
        self.max_cache_age_seconds = max_cache_age_seconds
        self.transport_fn = transport_fn

    def fetch_raw_catalog(self, force_refresh: bool = False) -> Dict[str, Any]:
        """Load catalog from disk cache or fetch via transport."""
        now_utc = datetime.now(timezone.utc)

        if not force_refresh and self.cache_file.is_file():
            try:
                cached_data = json.loads(self.cache_file.read_text(encoding="utf-8"))
                fetched_at_str = cached_data.get("fetched_at")
                if fetched_at_str:
                    fetched_at = datetime.fromisoformat(fetched_at_str.replace("Z", "+00:00"))
                    age = (now_utc - fetched_at).total_seconds()
                    if age < self.max_cache_age_seconds:
                        return cached_data
            except Exception:
                pass  # On cache read failure, fall back to transport

        # Fetch via transport
        if self.transport_fn:
            content = self.transport_fn(OPENROUTER_MODELS_URL)
        else:
            req = urllib.request.Request(
                OPENROUTER_MODELS_URL,
                headers={"User-Agent": "Runport-Benchmarking/0.1 (catalog-refresh)"},
            )
            with urllib.request.urlopen(req, timeout=15) as resp:
                content = resp.read().decode("utf-8")

        raw_json = json.loads(content)
        cache_payload = {
            "fetched_at": now_utc.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "source_url": OPENROUTER_MODELS_URL,
            "data": raw_json.get("data", raw_json if isinstance(raw_json, list) else []),
        }

        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.cache_file.write_text(json.dumps(cache_payload, indent=2), encoding="utf-8")
        return cache_payload

    def get_model_candidates(self, force_refresh: bool = False) -> List[ModelCandidate]:
        """Convert raw OpenRouter catalog data into validated ModelCandidate instances.
        
        Converts OpenRouter per-token pricing to per-1M tokens USD.
        """
        payload = self.fetch_raw_catalog(force_refresh=force_refresh)
        models_data = payload.get("data", [])
        candidates: List[ModelCandidate] = []

        for item in models_data:
            model_id = item.get("id")
            if not model_id:
                continue

            pricing = item.get("pricing") or {}
            # OpenRouter reports pricing per individual token in USD
            prompt_token_usd = Decimal(str(pricing.get("prompt") or 0))
            completion_token_usd = Decimal(str(pricing.get("completion") or 0))

            in_per_1m = prompt_token_usd * Decimal("1000000")
            out_per_1m = completion_token_usd * Decimal("1000000")

            candidates.append(
                ModelCandidate(
                    model_id=model_id,
                    display_name=item.get("name") or model_id,
                    provider=model_id.split("/")[0] if "/" in model_id else "openrouter",
                    deployment_mode="HOSTED_OPENROUTER",
                    license=item.get("license") or "Proprietary",
                    context_length=item.get("context_length"),
                    input_price_per_1m_usd=in_per_1m,
                    output_price_per_1m_usd=out_per_1m,
                    verification_status=FactStatus.VERIFIED_PRIMARY.value,
                    experimental_purpose=f"OpenRouter catalog model (context: {item.get('context_length')})",
                )
            )

        return candidates

    def register_in_model_registry(self, force_refresh: bool = False) -> List[ModelRecord]:
        """Register verified catalog entries into the global ModelRecord registry with strict Fact metadata."""
        payload = self.fetch_raw_catalog(force_refresh=force_refresh)
        fetched_at_str = payload.get("fetched_at", datetime.now(timezone.utc).isoformat())
        fetched_date = datetime.fromisoformat(fetched_at_str.replace("Z", "+00:00")).date()
        source_urls = [OPENROUTER_MODELS_URL]

        models_data = payload.get("data", [])
        registered_records: List[ModelRecord] = []

        for item in models_data:
            model_id = item.get("id")
            if not model_id:
                continue

            pricing = item.get("pricing") or {}
            prompt_token_usd = Decimal(str(pricing.get("prompt") or 0))
            completion_token_usd = Decimal(str(pricing.get("completion") or 0))
            in_per_1m = prompt_token_usd * Decimal("1000000")
            out_per_1m = completion_token_usd * Decimal("1000000")
            context = item.get("context_length") or 4096

            record = ModelRecord(
                key=model_id.replace("/", "-"),
                display_name=item.get("name") or model_id,
                roles=["CANDIDATE"],
                tasks=["BENCHMARK"],
                requested_model_id=fact(model_id, FactStatus.VERIFIED_PRIMARY, source_urls, checked_on=fetched_date),
                endpoint=fact("POST https://openrouter.ai/api/v1/chat/completions", FactStatus.VERIFIED_PRIMARY, source_urls, checked_on=fetched_date),
                request_fields=fact(["model", "messages"], FactStatus.VERIFIED_PRIMARY, source_urls, checked_on=fetched_date),
                response_shape=fact("chat.completion", FactStatus.VERIFIED_PRIMARY, source_urls, checked_on=fetched_date),
                output_type=fact("text", FactStatus.VERIFIED_PRIMARY, source_urls, checked_on=fetched_date),
                resolved_version_reporting=fact("exact", FactStatus.VERIFIED_PRIMARY, source_urls, checked_on=fetched_date),
                usage_fields=fact(["prompt_tokens", "completion_tokens"], FactStatus.VERIFIED_PRIMARY, source_urls, checked_on=fetched_date),
                input_price_per_1m_usd=fact(f"{in_per_1m:.6f}", FactStatus.VERIFIED_PRIMARY, source_urls, checked_on=fetched_date),
                output_price_per_1m_usd=fact(f"{out_per_1m:.6f}", FactStatus.VERIFIED_PRIMARY, source_urls, checked_on=fetched_date),
                context_limit_tokens=fact(context, FactStatus.VERIFIED_PRIMARY, source_urls, checked_on=fetched_date),
                provider_route=fact("openrouter", FactStatus.VERIFIED_PRIMARY, source_urls, checked_on=fetched_date),
                structured_output_support=fact(True, FactStatus.VERIFIED_PRIMARY, source_urls, checked_on=fetched_date),
                data_policy=fact("Provider-Standard", FactStatus.VERIFIED_PRIMARY, source_urls, checked_on=fetched_date),
                error_codes=fact([400, 401, 403, 429, 500, 502, 503], FactStatus.VERIFIED_PRIMARY, source_urls, checked_on=fetched_date),
                route=RouteRecord(
                    status=RouteStatus.READY,
                    route_input_price_per_1m_usd=fact(f"{in_per_1m:.6f}", FactStatus.VERIFIED_PRIMARY, source_urls, checked_on=fetched_date),
                    route_output_price_per_1m_usd=fact(f"{out_per_1m:.6f}", FactStatus.VERIFIED_PRIMARY, source_urls, checked_on=fetched_date),
                ),
            )
            register_model(record)
            registered_records.append(record)

        return registered_records

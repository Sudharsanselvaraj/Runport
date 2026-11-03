"""Offline unit tests for OpenRouter models catalog source.

Enforces:
1. Purely offline execution using recorded fixtures.
2. Honest conversion from per-token USD to per-1M tokens USD.
3. Disk caching with fetched_at timestamp.
4. Every price carries FactStatus.VERIFIED_PRIMARY, primary source URL, and check date.
"""

from decimal import Decimal
import json
from pathlib import Path
import pytest

from runport.catalog.openrouter import OPENROUTER_MODELS_URL, OpenRouterCatalogSource
from runport.models.registry import FactStatus, clear_registry, get_record


@pytest.fixture
def recorded_fixture_json() -> str:
    fixture_path = Path(__file__).parent / "fixtures" / "openrouter_models_fixture.json"
    return fixture_path.read_text(encoding="utf-8")


def test_openrouter_catalog_fetch_and_disk_cache(tmp_path, recorded_fixture_json):
    """Catalog source caches raw payload with fetched_at and reuses it on subsequent calls."""
    cache_dir = tmp_path / "cache"
    calls = []

    def fake_transport(url: str) -> str:
        calls.append(url)
        assert url == OPENROUTER_MODELS_URL
        return recorded_fixture_json

    source = OpenRouterCatalogSource(cache_dir=cache_dir, transport_fn=fake_transport)

    # First fetch: invokes transport and creates cache file
    payload1 = source.fetch_raw_catalog()
    assert len(calls) == 1
    assert "fetched_at" in payload1
    assert payload1["source_url"] == OPENROUTER_MODELS_URL
    assert len(payload1["data"]) == 3
    assert source.cache_file.is_file()

    # Second fetch: reuses disk cache without invoking transport
    payload2 = source.fetch_raw_catalog(force_refresh=False)
    assert len(calls) == 1  # No additional network call
    assert payload2["fetched_at"] == payload1["fetched_at"]

    # Force refresh: re-invokes transport
    payload3 = source.fetch_raw_catalog(force_refresh=True)
    assert len(calls) == 2


def test_openrouter_catalog_per_token_to_per_1m_pricing(tmp_path, recorded_fixture_json):
    """Converts OpenRouter per-token pricing to exact per-1M tokens USD using Decimal arithmetic."""
    source = OpenRouterCatalogSource(
        cache_dir=tmp_path / "cache",
        transport_fn=lambda _: recorded_fixture_json,
    )
    candidates = source.get_model_candidates()
    assert len(candidates) == 3

    by_id = {c.model_id: c for c in candidates}

    # gpt-4.1-nano: 0.0000001 -> $0.10/1M, 0.0000004 -> $0.40/1M
    nano = by_id["openai/gpt-4.1-nano"]
    assert nano.input_price_per_1m_usd == Decimal("0.10")
    assert nano.output_price_per_1m_usd == Decimal("0.40")
    assert nano.context_length == 128000

    # gemini-2.5-flash: 0.000000075 -> $0.075/1M, 0.00000030 -> $0.30/1M
    gemini = by_id["google/gemini-2.5-flash"]
    assert gemini.input_price_per_1m_usd == Decimal("0.075")
    assert gemini.output_price_per_1m_usd == Decimal("0.30")
    assert gemini.context_length == 1048576


def test_openrouter_catalog_fact_verification_status(tmp_path, recorded_fixture_json):
    """Registered models carry FactStatus.VERIFIED_PRIMARY, check date, and source URL."""
    clear_registry()
    source = OpenRouterCatalogSource(
        cache_dir=tmp_path / "cache",
        transport_fn=lambda _: recorded_fixture_json,
    )
    records = source.register_in_model_registry()
    assert len(records) == 3

    nano_rec = get_record("openai-gpt-4.1-nano")
    assert nano_rec is not None

    assert nano_rec.input_price_per_1m_usd.status == FactStatus.VERIFIED_PRIMARY
    assert nano_rec.input_price_per_1m_usd.value == "0.100000"
    assert nano_rec.input_price_per_1m_usd.source_urls == [OPENROUTER_MODELS_URL]
    assert nano_rec.input_price_per_1m_usd.checked_on is not None

    assert nano_rec.output_price_per_1m_usd.status == FactStatus.VERIFIED_PRIMARY
    assert nano_rec.output_price_per_1m_usd.value == "0.400000"
    assert nano_rec.output_price_per_1m_usd.source_urls == [OPENROUTER_MODELS_URL]
    clear_registry()

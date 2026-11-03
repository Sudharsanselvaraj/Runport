"""Registry honesty tests: nothing is VERIFIED without a source, and blockers are visible."""

from datetime import date
from decimal import Decimal
import pytest
from pydantic import ValidationError

from runport.models.registry import (
    Fact, FactStatus, ModelRecord, Protocol, RouteOption, RouteRecord, RouteStatus,
    clear_registry, estimate_permitted, fact, get_record, list_records, live_blockers,
    model_level_prices, observed, register_model, roster_status, unknown,
)


@pytest.fixture(autouse=True)
def clean_reg():
    clear_registry()
    yield
    clear_registry()


def test_fact_validation_rejects_unsourced_or_valued_unknowns():
    """Invariant: UNKNOWN must not carry a value, and verified facts must carry sources and dates."""
    # Unknown cannot carry a value
    with pytest.raises(ValidationError, match="an UNKNOWN fact must not carry a value"):
        Fact(value="x", status=FactStatus.UNKNOWN)

    # Verified primary needs sources
    with pytest.raises(ValidationError, match="needs source_urls"):
        Fact(value="x", status=FactStatus.VERIFIED_PRIMARY, checked_on=date(2026, 1, 1))

    # Verified primary needs checked_on
    with pytest.raises(ValidationError, match="needs checked_on"):
        Fact(value="x", status=FactStatus.VERIFIED_PRIMARY, source_urls=["https://example.com"])

    # User supplied is valid with checked_on even without URLs
    f_user = Fact(value="0.10", status=FactStatus.USER_SUPPLIED, checked_on=date(2026, 1, 1))
    assert f_user.value == "0.10"

    # Fully verified fact passes
    f_ok = fact("0.20", FactStatus.VERIFIED_PRIMARY, ["https://example.com/pricing"], checked_on=date(2026, 1, 1))
    assert f_ok.status == FactStatus.VERIFIED_PRIMARY
    assert f_ok.value == "0.20"
    assert f_ok.checked_on == date(2026, 1, 1)


def test_observed_fact_requires_complete_evidence():
    """Invariant: LIVE_OBSERVED facts require structured evidence and checked_on date."""
    with pytest.raises(ValidationError, match="LIVE_OBSERVED fact needs evidence"):
        Fact(value="res", status=FactStatus.LIVE_OBSERVED, source_urls=["https://example.com"], checked_on=date(2026, 1, 1))

    ev = {
        "run_ids": ["run-01"],
        "resolved_model_id": "model-v1-snapshot",
        "evidence_fields": {"tokens": "int"},
        "observed_at": "2026-01-01T00:00:00Z",
    }
    f_obs = observed("res", ["https://example.com"], ev, checked_on=date(2026, 1, 1))
    assert f_obs.status == FactStatus.LIVE_OBSERVED
    assert f_obs.evidence == ev


def test_dynamic_model_registration_and_blockers():
    """Registering model candidates dynamically populates roster and computes blockers."""
    d = date(2026, 1, 1)
    urls = ["https://example.com/model"]

    record = ModelRecord(
        key="candidate-1",
        display_name="Candidate 1",
        requested_model_id=fact("provider/cand-1", FactStatus.VERIFIED_PRIMARY, urls, d),
        endpoint=fact("POST https://api.example.com/v1/chat", FactStatus.VERIFIED_PRIMARY, urls, d),
        request_fields=fact(["model", "messages"], FactStatus.VERIFIED_PRIMARY, urls, d),
        response_shape=fact("chat.completion", FactStatus.VERIFIED_PRIMARY, urls, d),
        output_type=fact("text", FactStatus.VERIFIED_PRIMARY, urls, d),
        resolved_version_reporting=fact("exact", FactStatus.VERIFIED_PRIMARY, urls, d),
        usage_fields=fact(["prompt_tokens", "completion_tokens"], FactStatus.VERIFIED_PRIMARY, urls, d),
        input_price_per_1m_usd=fact("0.15", FactStatus.VERIFIED_PRIMARY, urls, d),
        output_price_per_1m_usd=fact("0.60", FactStatus.VERIFIED_PRIMARY, urls, d),
        context_limit_tokens=fact(128000, FactStatus.VERIFIED_PRIMARY, urls, d),
        provider_route=fact("Direct", FactStatus.VERIFIED_PRIMARY, urls, d),
        structured_output_support=fact(True, FactStatus.VERIFIED_PRIMARY, urls, d),
        data_policy=unknown("Pending audit"),
        error_codes=fact([400, 401, 429], FactStatus.VERIFIED_PRIMARY, urls, d),
        route=RouteRecord(status=RouteStatus.READY),
    )

    register_model(record)
    assert get_record("candidate-1") is not None
    assert len(list_records()) == 1

    # synthetic blockers are empty because all technical schema facts are VERIFIED_PRIMARY and route is READY
    assert live_blockers("candidate-1") == []

    # price estimation permitted
    assert estimate_permitted("provider/cand-1") is True
    assert model_level_prices("provider/cand-1") == (Decimal("0.15"), Decimal("0.60"))

    # Roster status reports readiness
    roster = roster_status()
    assert len(roster) == 1
    assert roster[0]["key"] == "candidate-1"
    assert roster[0]["readiness"] == "READY"

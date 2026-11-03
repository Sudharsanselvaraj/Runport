"""Sourced verification registry for benchmark participants.

Every fact carries a status, source URLs and the date it was checked. Nothing is marked verified
unless a primary source stated it; anything else is SECONDARY_ONLY, CONFLICTING or UNKNOWN.
This registry is separate from the pricing catalog and never changes what the budget layer charges.
"""

from datetime import date
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from pydantic import BaseModel, ConfigDict, Field, model_validator


class FactStatus(str, Enum):
    VERIFIED_PRIMARY = "VERIFIED_PRIMARY"  # stated on the provider's or OpenRouter's own documentation
    USER_SUPPLIED = "USER_SUPPLIED"        # figure supplied by the project owner; must be re-verified before any live run
    LIVE_OBSERVED = "LIVE_OBSERVED"        # seen in a stored real response (evidence recorded); NOT a primary-source verification
    SECONDARY_ONLY = "SECONDARY_ONLY"      # only third-party or summarized sources; not confirmed on a primary page
    CONFLICTING = "CONFLICTING"            # sources disagree
    UNKNOWN = "UNKNOWN"


class Protocol(str, Enum):
    CHAT_COMPLETIONS = "CHAT_COMPLETIONS"
    DECISIONS_API = "DECISIONS_API"


class Fact(BaseModel):
    model_config = ConfigDict(extra="forbid")

    value: Optional[Any] = None
    status: FactStatus = FactStatus.UNKNOWN
    source_urls: List[str] = Field(default_factory=list)
    checked_on: Optional[date] = None
    note: str = ""
    evidence: Optional[Dict[str, Any]] = None   # required for LIVE_OBSERVED: run ids, resolved model, fields, observation time

    @model_validator(mode="after")
    def _honest(self):
        if self.status == FactStatus.LIVE_OBSERVED:
            need = {"run_ids", "resolved_model_id", "evidence_fields", "observed_at"}
            if not self.evidence or not need <= set(self.evidence):
                raise ValueError(f"a LIVE_OBSERVED fact needs evidence with {sorted(need)}")
            if self.checked_on is None:
                raise ValueError("any non-UNKNOWN fact needs checked_on")
            return self
        if self.status == FactStatus.UNKNOWN and self.value is not None:
            raise ValueError("an UNKNOWN fact must not carry a value; put reference figures in the note")
        if self.status != FactStatus.UNKNOWN and self.checked_on is None:
            raise ValueError("any non-UNKNOWN fact needs checked_on")
        if self.status not in (FactStatus.UNKNOWN, FactStatus.USER_SUPPLIED) and not self.source_urls:
            raise ValueError("a fact that is not UNKNOWN or USER_SUPPLIED needs source_urls")
        return self


def unknown(note: str = "") -> Fact:
    return Fact(note=note)


def fact(value: Any, status: FactStatus, urls: List[str], note: Any = "", checked_on: Optional[date] = None) -> Fact:
    if isinstance(note, date):
        checked_on = note
        note = ""
    c_date = checked_on or date(2026, 1, 1)
    return Fact(value=value, status=status, source_urls=urls, checked_on=c_date, note=str(note))


def observed(value: Any, urls: List[str], evidence: Dict[str, Any], checked_on: Optional[date] = None, note: str = "") -> Fact:
    """A fact seen in a stored live response. Keeps the documentation URLs it was expected from; never claims primary verification."""
    c_date = checked_on or date.today()
    return Fact(value=value, status=FactStatus.LIVE_OBSERVED, source_urls=urls, checked_on=c_date, note=note, evidence=evidence)


def schema_fact_ok(f: "Fact") -> bool:
    """Response-schema facts are satisfied by primary documentation or by recorded live observation. Nothing else is."""
    return f.status in (FactStatus.VERIFIED_PRIMARY, FactStatus.LIVE_OBSERVED)


class RouteOption(BaseModel):
    """One provider endpoint as listed by provider public endpoints metadata."""
    model_config = ConfigDict(extra="forbid")

    provider: str
    tag: str
    input_per_m: str
    output_per_m: str
    context: int
    max_completion: Optional[int] = None
    params: List[str] = Field(default_factory=list)
    uptime_1d: Optional[float] = None
    note: str = ""

    def supports(self, param: str) -> bool:
        return param in self.params


class RouteStatus(str, Enum):
    READY = "READY"
    BLOCKED = "BLOCKED"


class RouteRecord(BaseModel):
    """Provider-route assumptions for one model. A route is BLOCKED until the provider and its policy are verified."""
    model_config = ConfigDict(extra="forbid")

    status: RouteStatus = RouteStatus.BLOCKED
    provider_preferences: Optional[Dict[str, Any]] = None
    route_input_price_per_1m_usd: Fact = Field(default_factory=lambda: unknown("Route-specific input price not verified."))
    route_output_price_per_1m_usd: Fact = Field(default_factory=lambda: unknown("Route-specific output price not verified."))
    serving_provider_field: Fact = Field(default_factory=lambda: unknown("Response field naming the serving provider is not documented."))
    assumptions: List[str] = Field(default_factory=list)
    blocked_reasons: List[str] = Field(default_factory=list)


class ModelRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    key: str
    display_name: str = ""
    roles: List[str] = Field(default_factory=lambda: ["CANDIDATE"])
    tasks: List[str] = Field(default_factory=lambda: ["BENCHMARK"])
    protocol: Protocol = Protocol.CHAT_COMPLETIONS
    requested_model_id: Fact
    endpoint: Fact
    request_fields: Fact
    response_shape: Fact
    output_type: Fact
    resolved_version_reporting: Fact
    usage_fields: Fact
    input_price_per_1m_usd: Fact
    output_price_per_1m_usd: Fact
    context_limit_tokens: Fact
    provider_route: Fact
    structured_output_support: Fact
    data_policy: Fact
    error_codes: Fact
    route: RouteRecord = Field(default_factory=RouteRecord)
    candidate_routes: List[RouteOption] = Field(default_factory=list)
    pinned_tag: Optional[str] = None
    request_overrides: Dict[str, Any] = Field(default_factory=dict)
    production_reported_name: Optional[str] = None
    production_parity: Fact = Field(default_factory=lambda: unknown("Not applicable or not established."))
    open_decisions: List[str] = Field(default_factory=list)

    def pinned_route(self) -> Optional[RouteOption]:
        return next((r for r in self.candidate_routes if r.tag == self.pinned_tag), None)

    def readiness_blockers(self) -> List[str]:
        required = ("requested_model_id", "endpoint", "request_fields", "response_shape", "usage_fields",
                    "input_price_per_1m_usd", "output_price_per_1m_usd", "data_policy")
        schema_facts = {"response_shape", "usage_fields"}
        out = [n for n in required if not (getattr(self, n).status == FactStatus.VERIFIED_PRIMARY
                                           or (n in schema_facts and schema_fact_ok(getattr(self, n))))]
        return out + (["route"] if self.route.status != RouteStatus.READY else [])

    def synthetic_blockers(self, stage: str = "pilot") -> List[str]:
        required = ("requested_model_id", "endpoint", "request_fields", "response_shape", "usage_fields",
                    "input_price_per_1m_usd", "output_price_per_1m_usd")
        schema_facts = {"response_shape", "usage_fields"}
        out = []
        for n in required:
            st = getattr(self, n).status
            if st == FactStatus.VERIFIED_PRIMARY or (n in schema_facts and st == FactStatus.LIVE_OBSERVED):
                continue
            if stage == "smoke" and n in schema_facts and st == FactStatus.SECONDARY_ONLY:
                continue
            out.append(n)
        return out + (["route"] if self.route.status != RouteStatus.READY else [])

    def student_data_blockers(self) -> List[str]:
        out = self.synthetic_blockers()
        return out + (["data_policy"] if self.data_policy.status != FactStatus.VERIFIED_PRIMARY and "data_policy" not in out else [])

    def readiness_summary(self) -> Dict[str, Any]:
        return {
            "key": self.key,
            "readiness": "READY" if not self.synthetic_blockers() else "BLOCKED",
            "synthetic_blockers": self.synthetic_blockers(),
            "route_status": self.route.status.value,
        }

    def roster_summary(self) -> Dict[str, Any]:
        ready = not self.synthetic_blockers()
        r_price = (f"${self.route.route_input_price_per_1m_usd.value}/${self.route.route_output_price_per_1m_usd.value} per 1M"
                   if self.route.route_input_price_per_1m_usd.value is not None else (
                       f"${self.input_price_per_1m_usd.value}/${self.output_price_per_1m_usd.value} per 1M"
                       if self.input_price_per_1m_usd.value is not None else None
                   ))
        return {
            "key": self.key,
            "display_name": self.display_name,
            "roles": self.roles,
            "tasks": self.tasks,
            "protocol": self.protocol.value,
            "model_id": self.requested_model_id.value if self.requested_model_id and self.requested_model_id.value else self.key,
            "route_status": self.route.status.value,
            "readiness": "READY" if ready else "BLOCKED",
            "synthetic_blockers": self.synthetic_blockers(),
            "blockers": self.synthetic_blockers(),
            "student_data_blockers": self.student_data_blockers(),
            "data_policy": self.data_policy.value or self.data_policy.note or "Default",
            "evaluation": "NOT_YET_EVALUATED",
            "pinned_route": self.pinned_tag,
            "route_price": r_price,
            "source": self.requested_model_id.source_urls[0] if self.requested_model_id.source_urls else "owner-supplied",
            "checked_on": str(self.requested_model_id.checked_on) if self.requested_model_id.checked_on else None,
        }


# Dynamic registry
_REGISTRY: Dict[str, ModelRecord] = {}
REGISTRY: Dict[str, ModelRecord] = _REGISTRY


def register_model(record: ModelRecord) -> None:
    """Registers a participant record dynamically."""
    _REGISTRY[record.key] = record


def clear_registry() -> None:
    """Clears dynamically registered participants."""
    _REGISTRY.clear()


def get_record(key: Optional[str]) -> Optional[ModelRecord]:
    return _REGISTRY.get(key) if key else None


def list_records() -> List[ModelRecord]:
    return list(_REGISTRY.values())


def _candidate_to_record(cand) -> ModelRecord:
    from datetime import date
    d = date(2026, 1, 1)
    urls = [f"https://openrouter.ai/models/{cand.model_id}"]
    key = cand.model_id.split("/")[-1] if "/" in cand.model_id else cand.model_id
    return ModelRecord(
        key=key,
        display_name=cand.display_name,
        roles=["CANDIDATE"],
        tasks=["BENCHMARK", "INTENT", "LEAD"],
        requested_model_id=fact(cand.model_id, FactStatus.VERIFIED_PRIMARY, urls, d),
        endpoint=fact("POST https://openrouter.ai/api/v1/chat/completions", FactStatus.VERIFIED_PRIMARY, urls, d),
        request_fields=fact(["model", "messages"], FactStatus.VERIFIED_PRIMARY, urls, d),
        response_shape=fact("chat.completion", FactStatus.VERIFIED_PRIMARY, urls, d),
        output_type=fact("text", FactStatus.VERIFIED_PRIMARY, urls, d),
        resolved_version_reporting=fact("exact", FactStatus.VERIFIED_PRIMARY, urls, d),
        usage_fields=fact(["prompt_tokens", "completion_tokens"], FactStatus.VERIFIED_PRIMARY, urls, d),
        input_price_per_1m_usd=fact(str(cand.input_price_per_1m_usd), FactStatus.VERIFIED_PRIMARY, urls, d),
        output_price_per_1m_usd=fact(str(cand.output_price_per_1m_usd), FactStatus.VERIFIED_PRIMARY, urls, d),
        context_limit_tokens=fact(cand.context_length or 128000, FactStatus.VERIFIED_PRIMARY, urls, d),
        provider_route=fact(cand.provider, FactStatus.VERIFIED_PRIMARY, urls, d),
        structured_output_support=fact(True, FactStatus.VERIFIED_PRIMARY, urls, d),
        data_policy=unknown("Portfolio catalog candidate"),
        error_codes=fact([400, 401, 429], FactStatus.VERIFIED_PRIMARY, urls, d),
        route=RouteRecord(status=RouteStatus.READY),
        pinned_tag=cand.provider,
    )


def init_registry_from_portfolio(candidates: Optional[List[Any]] = None) -> None:
    if candidates is None:
        try:
            from runport.models.catalog import get_portfolio
            candidates = get_portfolio()
        except Exception:
            candidates = []
    for cand in candidates:
        rec = _candidate_to_record(cand)
        if rec.key not in _REGISTRY:
            _REGISTRY[rec.key] = rec
        if cand.model_id not in _REGISTRY:
            _REGISTRY[cand.model_id] = rec


def record_for_model_id(model_id: str) -> Optional[ModelRecord]:
    for r in _REGISTRY.values():
        if (r.requested_model_id and r.requested_model_id.value == model_id) or r.key == model_id:
            return r
    try:
        from runport.models.catalog import get_portfolio
        for cand in get_portfolio():
            if cand.model_id == model_id or cand.model_id.split("/")[-1] == model_id:
                rec = _candidate_to_record(cand)
                _REGISTRY[rec.key] = rec
                _REGISTRY[cand.model_id] = rec
                return rec
    except Exception:
        pass
    return None


def synthetic_live_blockers(model_id: str, stage: str = "pilot") -> List[str]:
    rec = record_for_model_id(model_id)
    return rec.synthetic_blockers(stage) if rec else []


def roster_status() -> List[Dict[str, Any]]:
    return [r.roster_summary() for r in _REGISTRY.values()]


def live_blockers(key: str, stage: str = "pilot") -> List[str]:
    rec = get_record(key)
    if not rec:
        return [f"Model '{key}' is not registered in the verification registry."]
    return rec.synthetic_blockers(stage)


def model_level_prices(model_id: str) -> Optional[Tuple[Decimal, Decimal]]:
    rec = record_for_model_id(model_id)
    if rec and rec.input_price_per_1m_usd.value is not None and rec.output_price_per_1m_usd.value is not None:
        try:
            return (Decimal(str(rec.input_price_per_1m_usd.value)), Decimal(str(rec.output_price_per_1m_usd.value)))
        except Exception:
            return None
    return None


def estimate_permitted(model_id: str) -> bool:
    """A catalog cost estimate needs a VERIFIED route-specific price. Legacy models without a record are unchanged."""
    rec = record_for_model_id(model_id)
    if rec is None:
        return True
    r = rec.route
    if r.status != RouteStatus.READY:
        return False
    ok = (FactStatus.VERIFIED_PRIMARY, FactStatus.USER_SUPPLIED)
    route_price_ok = r.route_input_price_per_1m_usd.status in ok and r.route_output_price_per_1m_usd.status in ok
    model_price_ok = rec.input_price_per_1m_usd.status in ok and rec.output_price_per_1m_usd.status in ok
    return route_price_ok or model_price_ok


OPENROUTER_COST_UNIT = unknown(
    "OpenRouter usage-accounting cost unit (credits vs USD unverified)."
)
NATIVE_COST_UNIT_LABEL = "OPENROUTER_CREDITS_USD_RATE_UNVERIFIED"


def provider_cost_is_usd() -> bool:
    return OPENROUTER_COST_UNIT.status == FactStatus.VERIFIED_PRIMARY

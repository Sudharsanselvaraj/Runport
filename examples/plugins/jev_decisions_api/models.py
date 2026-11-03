"""Models and contracts for Jev Decisions API reference plugin."""

from enum import Enum
from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, ConfigDict, Field


class IntentLabel(str, Enum):
    """Reference Intent labels."""
    GREETING = "GREETING"
    OUT_OF_SCOPE = "OUT_OF_SCOPE"
    UPLOAD_STATUS_CHECK = "UPLOAD_STATUS_CHECK"
    HUMAN_HANDOFF_REQUEST = "HUMAN_HANDOFF_REQUEST"
    QUERY = "QUERY"


class Task(str, Enum):
    INTENT = "INTENT"
    LEAD = "LEAD"


class Protocol(str, Enum):
    CHAT_COMPLETIONS = "CHAT_COMPLETIONS"
    DECISIONS_API = "DECISIONS_API"


class InvalidReason(str, Enum):
    EMPTY_OUTPUT = "EMPTY_OUTPUT"
    UNKNOWN_LABEL = "UNKNOWN_LABEL"
    EXTRA_TEXT = "EXTRA_TEXT"
    WRONG_CASE = "WRONG_CASE"


class IntentValidation(BaseModel):
    valid: bool
    label: Optional[IntentLabel] = None
    reason: Optional[InvalidReason] = None


_LABELS = {l.value: l for l in IntentLabel}
_UPPER = {l.value.upper() for l in IntentLabel}


def validate_intent_output(raw: Optional[str]) -> IntentValidation:
    """Validate intent label against reference labels."""
    if raw is None or not raw.strip():
        return IntentValidation(valid=False, reason=InvalidReason.EMPTY_OUTPUT)
    text = raw.strip()
    if text in _LABELS:
        return IntentValidation(valid=True, label=_LABELS[text])
    if text.upper() in _UPPER:
        return IntentValidation(valid=False, reason=InvalidReason.WRONG_CASE)
    return IntentValidation(valid=False, reason=InvalidReason.UNKNOWN_LABEL)


class AdapterResult(BaseModel):
    """What one protocol adapter returns for one case."""
    model_config = ConfigDict(extra="forbid")

    ok: bool
    task: Task
    protocol: Protocol
    requested_model_id: str
    issues: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    resolved_model_id: Optional[str] = None
    serving_provider: Optional[str] = None
    requested_route: Optional[Dict[str, Any]] = None
    predicted_label: Optional[IntentLabel] = None
    predicted_need_cta: Optional[bool] = None
    raw_output: Optional[str] = None
    label_probs: Optional[Dict[str, float]] = None
    native_confidence: Optional[float] = None
    confidence_source: str = "NONE"
    yes_prob: Optional[float] = None
    prompt_tokens: Optional[int] = None
    completion_tokens: Optional[int] = None
    usage_source: Literal["PROVIDER_REPORTED", "PARTIAL", "UNAVAILABLE"] = "UNAVAILABLE"
    latency_ms: Optional[float] = None
    attempt_latency_ms: Optional[float] = None
    model_latency_ms: Optional[float] = None


"""Adapter results and persisted prediction records.

Nullable means unavailable: tokens, latency, confidence and cost are never fabricated. A prediction is never ground
truth: records carry no expected label and `is_ground_truth` can only be False.
"""

import json
from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional, Set, Tuple

from pydantic import BaseModel, ConfigDict, Field

from runport.classification.contracts import CONTRACT_VERSION, PARITY_STATUS
from runport.models.registry import Protocol
from runport.providers.base import scrub_secrets

ConfidenceSource = Literal["NATIVE_DISTRIBUTION", "NATIVE_CONFIDENCE_FIELD", "NONE"]


class Task(str, Enum):
    """General workload task types."""
    CLASSIFICATION = "classification"
    BENCHMARK = "benchmark"
    RAG = "rag"


class AdapterResult(BaseModel):
    """What one protocol adapter returns for one case. `ok` is False when output or envelope failed validation."""
    model_config = ConfigDict(extra="forbid")

    ok: bool
    task: str = "classification"
    protocol: Protocol = Protocol.CHAT_COMPLETIONS
    requested_model_id: str
    issues: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    resolved_model_id: Optional[str] = None
    serving_provider: Optional[str] = None
    requested_route: Optional[Dict[str, Any]] = None
    predicted_label: Optional[str] = None
    raw_output: Optional[str] = None
    label_probs: Optional[Dict[str, float]] = None
    native_confidence: Optional[float] = None
    confidence_source: ConfidenceSource = "NONE"
    yes_prob: Optional[float] = None
    prompt_tokens: Optional[int] = None
    completion_tokens: Optional[int] = None
    usage_source: Literal["PROVIDER_REPORTED", "PARTIAL", "UNAVAILABLE"] = "UNAVAILABLE"
    latency_ms: Optional[float] = None
    attempt_latency_ms: Optional[float] = None
    model_latency_ms: Optional[float] = None
    attempts: int = Field(default=1, ge=1)
    retry_errors: List[str] = Field(default_factory=list)
    native_cost: Optional[Decimal] = None
    native_cost_unit: Optional[str] = None
    finish_reason: Optional[str] = None
    reasoning_tokens: Optional[int] = None
    actual_cost_usd: Optional[Decimal] = None
    estimated_cost_usd: Optional[Decimal] = None
    cost_usd: Decimal = Decimal("0")
    cost_basis: Literal["PROVIDER_REPORTED", "ESTIMATED_FROM_CATALOG", "UNAVAILABLE"] = "UNAVAILABLE"


class PredictionRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    record_id: str
    run_id: str
    case_id: str
    task: str = "classification"
    model_key: str
    protocol: Protocol = Protocol.CHAT_COMPLETIONS
    requested_model_id: str
    prompt_version: str
    dataset_version: str
    status: Literal["OK", "INVALID_OUTPUT", "ERROR", "TIMEOUT", "SKIPPED_POLICY"]
    attempts: int = 1
    retry_errors: List[str] = Field(default_factory=list)
    resolved_model_id: Optional[str] = None
    serving_provider: Optional[str] = None
    requested_route: Optional[Dict[str, Any]] = None
    predicted_label: Optional[str] = None
    raw_output: Optional[str] = None
    label_probs: Optional[Dict[str, float]] = None
    native_confidence: Optional[float] = None
    confidence_source: ConfidenceSource = "NONE"
    yes_prob: Optional[float] = None
    prompt_tokens: Optional[int] = None
    completion_tokens: Optional[int] = None
    usage_source: Literal["PROVIDER_REPORTED", "PARTIAL", "UNAVAILABLE"] = "UNAVAILABLE"
    latency_ms: Optional[float] = None
    attempt_latency_ms: Optional[float] = None
    model_latency_ms: Optional[float] = None
    actual_cost_usd: Optional[Decimal] = None
    estimated_cost_usd: Optional[Decimal] = None
    cost_usd: Decimal = Decimal("0")
    cost_basis: Literal["PROVIDER_REPORTED", "ESTIMATED_FROM_CATALOG", "UNAVAILABLE"] = "UNAVAILABLE"
    error_type: Optional[str] = None
    error_message: Optional[str] = None
    is_ground_truth: Literal[False] = False
    created_at: str
    native_cost: Optional[Decimal] = None
    native_cost_unit: Optional[str] = None
    input_contract_version: str = CONTRACT_VERSION
    parity_status: str = PARITY_STATUS
    validation_issues: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    finish_reason: Optional[str] = None
    reasoning_tokens: Optional[int] = None
    recorded_cost_usd: Optional[Decimal] = None

    def to_json_line(self) -> str:
        return self.to_jsonl_row()

    def to_jsonl_row(self) -> str:
        d = self.model_dump()
        d["cost_usd"] = f"{self.cost_usd:.6f}"
        if self.actual_cost_usd is not None:
            d["actual_cost_usd"] = f"{self.actual_cost_usd:.6f}"
        if self.estimated_cost_usd is not None:
            d["estimated_cost_usd"] = f"{self.estimated_cost_usd:.6f}"
        if self.native_cost is not None:
            d["native_cost"] = f"{self.native_cost:.6f}"
        if self.recorded_cost_usd is not None:
            d["recorded_cost_usd"] = f"{self.recorded_cost_usd:.6f}"
        if self.requested_route:
            d["requested_route"] = scrub_secrets(self.requested_route)
        return json.dumps(d)


class PredictionStore:
    """Append-only store for prediction records."""

    def __init__(self, path: Path):
        self.path = Path(path)

    def append(self, rec: PredictionRecord) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as f:
            f.write(rec.to_jsonl_row() + "\n")

    def load(self) -> List[PredictionRecord]:
        if not self.path.exists():
            return []
        recs = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                recs.append(PredictionRecord.model_validate_json(line))
        return recs

    def read_all(self) -> List[PredictionRecord]:
        return self.load()

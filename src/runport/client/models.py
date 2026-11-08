"""Typed client models for Runport Remote Python Client.

Specification: docs/SDK_API_CONTRACT.md section 2.3.
Invariants:
- Null is not 0: missing measurements remain None / UNAVAILABLE.
"""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class TargetItem(BaseModel):
    model_config = ConfigDict(extra="ignore")

    target_id: str
    name: str
    target_type: str
    provider: str
    license: Optional[str] = None
    context_length: Optional[int] = None
    input_price_per_1m_usd: Optional[float] = None
    output_price_per_1m_usd: Optional[float] = None
    verification_status: Optional[str] = None
    billing: str = "metered"


class DatasetItem(BaseModel):
    model_config = ConfigDict(extra="ignore")

    filename: str
    case_count: int
    size_bytes: int
    path: Optional[str] = None
    message: Optional[str] = None


class Plan(BaseModel):
    model_config = ConfigDict(extra="ignore")

    plan_id: str
    plan_fingerprint: str
    status: str
    expires_at: float
    target_ids: List[str]
    case_count: int
    dataset_label: str
    projected_max_cost_usd: Optional[str] = None
    per_target: List[Dict[str, Any]] = Field(default_factory=list)
    blockers: List[str] = Field(default_factory=list)
    confirmation_phrase: str
    requested_by: str = "api"
    approved_by: Optional[str] = None


class Job(BaseModel):
    model_config = ConfigDict(extra="ignore")

    job_id: str
    plan_id: str
    run_id: Optional[str] = None
    status: str
    total_cases: int = 0
    completed_cases: int = 0
    failed_cases: int = 0
    booked_spend_usd: Optional[str] = None
    error_message: Optional[str] = None
    cancelled: bool = False
    created_at: str
    updated_at: str
    finished_at: Optional[str] = None

    @property
    def is_finished(self) -> bool:
        return self.status in ("completed", "failed", "cancelled")


class Run(BaseModel):
    model_config = ConfigDict(extra="ignore")

    run_id: str
    timestamp: str
    model_id: str
    dataset_path: str
    total_cases: int
    completed_cases: int
    failed_cases: int
    total_cost_usd: str
    mean_latency_ms: Optional[float] = None
    mean_accuracy: Optional[float] = None
    mean_groundedness: Optional[float] = None
    mean_overall_score: Optional[float] = None
    is_dry_run: bool = False
    notes: Optional[str] = None


class ScoreItem(BaseModel):
    model_config = ConfigDict(extra="ignore")

    name: str
    kind: str
    value: Optional[float] = None
    evaluator: str


class Result(BaseModel):
    model_config = ConfigDict(extra="ignore")

    result_id: str
    run_id: str
    case_id: str
    model_id: str
    prediction: Optional[str] = None
    ground_truth: Optional[str] = None
    is_correct: Optional[bool] = None
    cost_usd: Optional[str] = None
    cost_basis: str
    latency_ms: Optional[float] = None
    scores: List[ScoreItem] = Field(default_factory=list)


class BudgetPolicyInfo(BaseModel):
    model_config = ConfigDict(extra="ignore")
    total_budget_usd: float
    pilot_budget_usd: float
    per_run_ceiling_usd: float
    per_case_ceiling_usd: float
    require_priced: bool


class BudgetSpendInfo(BaseModel):
    model_config = ConfigDict(extra="ignore")
    total_spent_usd: float
    pilot_spent_usd: float
    remaining_total_usd: float
    remaining_pilot_usd: float


class BudgetStatus(BaseModel):
    model_config = ConfigDict(extra="ignore")

    policy: BudgetPolicyInfo
    spend: BudgetSpendInfo
    unresolved_count: int
    unresolved_transactions: List[Dict[str, Any]] = Field(default_factory=list)

    @property
    def unresolved_blocked(self) -> bool:
        return self.unresolved_count > 0

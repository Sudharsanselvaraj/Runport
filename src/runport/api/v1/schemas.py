"""Pydantic v2 schemas for Runport REST API v1.

Specification: docs/SDK_API_CONTRACT.md section 2.
Enforces strict invariants:
- 'Null is not 0': missing telemetry fields remain None, never fabricated to zero.
- Decimal string representation for financial costs.
- Explicit status and provenance vocabularies.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


# =============================================================================
# Targets & Models Schemas
# =============================================================================


class TargetItem(BaseModel):
    model_config = ConfigDict(extra="ignore")

    target_id: str = Field(..., description="Unique target identifier")
    name: str = Field(..., description="Display name")
    target_type: str = Field(..., description="Target category (model, workflow, agent, etc.)")
    provider: Optional[str] = Field(default=None, description="Hosting provider or execution engine")
    license: Optional[str] = Field(default=None, description="Software or model license")
    context_length: Optional[int] = Field(default=None, description="Context window size in tokens")
    input_price_per_1m_usd: Optional[float] = Field(default=None, description="Verified price per 1M input tokens")
    output_price_per_1m_usd: Optional[float] = Field(default=None, description="Verified price per 1M output tokens")
    verification_status: Optional[str] = Field(default=None, description="Catalog verification state")
    billing: Optional[str] = Field(default=None, description="Billing mode: local, metered, subscription, unpriced")


# =============================================================================
# Datasets Schemas
# =============================================================================


class DatasetSummaryItem(BaseModel):
    model_config = ConfigDict(extra="ignore")

    filename: str = Field(..., description="Dataset file name")
    path: str = Field(..., description="Absolute filesystem path")
    size_bytes: int = Field(..., description="File size in bytes")
    case_count: int = Field(..., description="Total non-empty evaluation cases")


class DatasetUploadResponse(BaseModel):
    filename: str
    size_bytes: int
    case_count: int
    message: str = "Dataset uploaded and verified successfully."


# =============================================================================
# Planning Schemas
# =============================================================================


class PlanCreateRequest(BaseModel):
    target_ids: List[str] = Field(min_length=1, description="List of target IDs to evaluate")
    dataset_name: str = Field(..., min_length=1, description="Dataset file name inside data/evaluation/")
    sample_size: Optional[int] = Field(default=None, ge=1, description="Optional case limit for evaluation")
    is_pilot: bool = Field(default=True, description="Whether to book against pilot budget ceiling")


class TargetPlanSummary(BaseModel):
    target_id: str
    type: str
    billing: str
    priced: bool
    projected_cost_usd: Optional[str] = None
    pricing_rule: Optional[str] = None


class PlanResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    plan_id: str = Field(..., description="Unique plan identifier")
    plan_fingerprint: str = Field(..., description="Cryptographic SHA-256 plan fingerprint")
    status: str = Field(..., description="Plan state: PENDING, APPROVED, CONSUMED, EXPIRED")
    expires_at: float = Field(..., description="Unix epoch timestamp when plan approval expires")
    target_ids: List[str] = Field(..., description="Candidate target identifiers")
    case_count: int = Field(..., description="Number of evaluation cases")
    dataset_label: str = Field(..., description="Dataset identifier")
    projected_max_cost_usd: Optional[str] = Field(default=None, description="Projected worst-case USD spend")
    per_target: List[Dict[str, Any]] = Field(default_factory=list, description="Cost breakdown per target")
    blockers: List[str] = Field(default_factory=list, description="Preflight blockers preventing execution")
    confirmation_phrase: str = Field(..., description="Typed approval phrase required for human authorization")
    requested_by: str = Field(default="api", description="Plan requestor")
    approved_by: Optional[str] = Field(default=None, description="Approver identity if authorized")


class PlanApproveRequest(BaseModel):
    fingerprint: str = Field(..., min_length=1, description="SHA-256 fingerprint matching the plan")
    approver: str = Field(default="operator", description="Operator identity granting approval")


# =============================================================================
# Run & Job Execution Schemas
# =============================================================================


class RunSubmitRequest(BaseModel):
    idempotency_key: Optional[str] = Field(default=None, description="Optional idempotency key to prevent duplicate runs")
    sample_size: Optional[int] = Field(default=None, ge=1, description="Optional override of evaluation case count")


class RunJobResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    job_id: str = Field(..., description="Unique job execution identifier")
    plan_id: str = Field(..., description="Associated execution plan ID")
    run_id: Optional[str] = Field(default=None, description="Associated evaluation run ID once started")
    status: str = Field(..., description="Job status: queued, running, completed, failed, cancelled")
    total_cases: int = Field(default=0, description="Total cases to execute")
    completed_cases: int = Field(default=0, description="Cases completed so far")
    failed_cases: int = Field(default=0, description="Cases that encountered errors")
    booked_spend_usd: Optional[str] = Field(default=None, description="Total spend booked so far")
    error_message: Optional[str] = Field(default=None, description="Error details if job failed")
    cancelled: bool = Field(default=False, description="Whether cancellation was requested")
    created_at: str = Field(..., description="Job submission timestamp in UTC")
    updated_at: str = Field(..., description="Last progress update timestamp in UTC")
    finished_at: Optional[str] = Field(default=None, description="Completion timestamp in UTC")


class RunDetailResponse(BaseModel):
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


class RunResultItem(BaseModel):
    model_config = ConfigDict(extra="ignore")

    result_id: Optional[str] = None
    case_id: str
    prompt: str
    generated_output: Optional[str] = None
    latency_ms: Optional[float] = None
    prompt_tokens: Optional[int] = None
    completion_tokens: Optional[int] = None
    cost_usd: Optional[str] = None
    cost_basis: Optional[str] = None
    accuracy: Optional[float] = None
    score_kind: Optional[str] = None
    trace_id: Optional[str] = None


class RunResultsListResponse(BaseModel):
    run_id: str
    total_cases: int
    results: List[RunResultItem]


# =============================================================================
# Budget Schemas
# =============================================================================


class BudgetPolicyInfo(BaseModel):
    total_budget_usd: float
    pilot_budget_usd: float
    per_run_ceiling_usd: float
    per_case_ceiling_usd: float
    require_priced: bool


class BudgetSpendInfo(BaseModel):
    total_spent_usd: float
    pilot_spent_usd: float
    remaining_total_usd: float
    remaining_pilot_usd: float


class BudgetStatusResponse(BaseModel):
    policy: BudgetPolicyInfo
    spend: BudgetSpendInfo
    unresolved_count: int
    unresolved_transactions: List[Dict[str, Any]]

"""Unified Target and TargetResult abstractions for Runport.

Every system evaluated by Runport — whether a raw model completion, system prompt,
autonomous agent, or multi-step workflow pipeline — implements the Target protocol.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, Iterator, List, Optional


class TargetType(str, Enum):
    RAW_MODEL = "raw_model"
    WORKFLOW_HTTP = "workflow_http"
    WORKFLOW_DIFY = "workflow_dify"
    WORKFLOW_FLOWISE = "workflow_flowise"
    WORKFLOW_LANGFLOW = "workflow_langflow"
    WORKFLOW_N8N = "workflow_n8n"
    WORKFLOW_LANGGRAPH = "workflow_langgraph"
    PYTHON_CALLABLE = "python_callable"
    SUBPROCESS = "subprocess"


class TargetStatus(str, Enum):
    SUCCESS = "success"
    FAILED = "failed"
    TIMEOUT = "timeout"
    RATE_LIMITED = "rate_limited"
    UNAUTHORIZED = "unauthorized"
    INVALID_OUTPUT = "invalid_output"


class CostBasis(str, Enum):
    ACTUAL = "ACTUAL"            # Exact provider-reported cost
    ESTIMATED = "ESTIMATED"      # Catalog price * reported tokens
    UNRESOLVED = "UNRESOLVED"    # Billed request with unknown cost
    UNAVAILABLE = "UNAVAILABLE"  # Zero-cost unpriced / local execution


@dataclass(frozen=True)
class TargetPricing:
    """Pricing configuration for a target in USD per 1M tokens or per request."""
    input_usd_per_1m: Optional[Decimal] = None
    output_usd_per_1m: Optional[Decimal] = None
    fixed_usd_per_request: Optional[Decimal] = None

    def calculate_cost(
        self,
        tokens_in: Optional[int],
        tokens_out: Optional[int],
    ) -> Optional[Decimal]:
        """Calculates estimated cost given token usage."""
        cost = Decimal("0.0")
        has_pricing = False

        if self.fixed_usd_per_request is not None:
            cost += self.fixed_usd_per_request
            has_pricing = True

        if tokens_in is not None and self.input_usd_per_1m is not None:
            cost += (Decimal(tokens_in) / Decimal("1000000")) * self.input_usd_per_1m
            has_pricing = True

        if tokens_out is not None and self.output_usd_per_1m is not None:
            cost += (Decimal(tokens_out) / Decimal("1000000")) * self.output_usd_per_1m
            has_pricing = True

        return cost if has_pricing else None


@dataclass
class TargetResult:
    """Standardized result returned by any target execution."""
    target_id: str
    status: TargetStatus
    output_text: Optional[str] = None
    raw_output: Any = None
    latency_ms: Optional[float] = None
    tokens_in: Optional[int] = None
    tokens_out: Optional[int] = None
    cost_usd: Optional[Decimal] = None
    cost_basis: CostBasis = CostBasis.UNAVAILABLE
    is_replay: bool = False
    provenance: str = "LIVE"
    error_message: Optional[str] = None
    error_code: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def is_success(self) -> bool:
        return self.status == TargetStatus.SUCCESS and self.output_text is not None


@dataclass
class TargetChunk:
    """Streaming chunk emitted by a streaming target."""
    target_id: str
    delta_text: str
    is_final: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)


class Target(ABC):
    """Abstract base class for all Runport benchmark targets."""

    def __init__(
        self,
        target_id: str,
        name: str,
        target_type: TargetType,
        capabilities: Optional[List[str]] = None,
        pricing: Optional[TargetPricing] = None,
        timeout_seconds: float = 30.0,
        max_retries: int = 3,
    ) -> None:
        self.target_id = target_id
        self.name = name
        self.target_type = target_type
        self.capabilities = capabilities or ["text"]
        self.pricing = pricing
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries

    @abstractmethod
    def execute(
        self,
        input_payload: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None,
    ) -> TargetResult:
        """Executes a single benchmark request and returns a normalized TargetResult."""
        pass

    def execute_stream(
        self,
        input_payload: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None,
    ) -> Iterator[TargetChunk]:
        """Optionally streams results. Default implementation wraps execute()."""
        res = self.execute(input_payload, context)
        yield TargetChunk(
            target_id=self.target_id,
            delta_text=res.output_text or "",
            is_final=True,
            metadata=res.metadata,
        )


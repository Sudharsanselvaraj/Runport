"""Unified Target and TargetResult abstractions for Runport.

Every system evaluated by Runport — whether a raw model completion, system prompt,
autonomous agent, or multi-step workflow pipeline — implements the Target protocol.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, Iterator, List, Optional
from urllib.parse import urlparse


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
    MCP_TOOL = "mcp_tool"


class TargetStatus(str, Enum):
    SUCCESS = "success"
    FAILED = "failed"
    TIMEOUT = "timeout"
    RATE_LIMITED = "rate_limited"
    UNAUTHORIZED = "unauthorized"
    INVALID_OUTPUT = "invalid_output"


class CostBasis(str, Enum):
    ACTUAL = "ACTUAL"  # Exact provider-reported cost
    ESTIMATED = "ESTIMATED"  # Catalog price * reported tokens
    UNRESOLVED = "UNRESOLVED"  # Billed request with unknown cost
    UNAVAILABLE = "UNAVAILABLE"  # Zero-cost unpriced / local execution


class BillingMode(str, Enum):
    """Whether a target's requests can cost money. Decides how a missing cost is booked.

    LOCAL     Runs in this process, as a local subprocess, or on a loopback address. A missing cost is booked
              as UNAVAILABLE ($0.00 local execution).
    UNBILLED  A remote endpoint the operator has explicitly declared free. Booked like LOCAL.
    BILLABLE  A remote endpoint that may charge. A missing cost is booked as UNRESOLVED and blocks further
              live execution until reconciled. This is the default for anything Runport cannot prove local.
    """

    LOCAL = "local"
    UNBILLED = "unbilled"
    BILLABLE = "billable"


_LOOPBACK_HOSTS = frozenset({"localhost", "127.0.0.1", "::1", "0:0:0:0:0:0:0:1"})


def billing_for_url(url: Optional[str], declared: Optional["BillingMode"] = None) -> "BillingMode":
    """Billing mode for a URL-addressed target: the operator's declaration wins, loopback is LOCAL, anything else BILLABLE."""
    if declared is not None:
        return BillingMode(declared)
    host = (urlparse(url or "").hostname or "").lower()
    if host in _LOOPBACK_HOSTS or host.startswith("127.") or host.endswith(".localhost"):
        return BillingMode.LOCAL
    return BillingMode.BILLABLE


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
    # False only when the target is certain nothing left this machine (e.g. a missing API key was caught before
    # sending). None means unknown, which the runner treats as "possibly sent".
    request_sent: Optional[bool] = None

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
        billing: BillingMode = BillingMode.BILLABLE,
    ) -> None:
        self.target_id = target_id
        self.billing = BillingMode(billing)
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

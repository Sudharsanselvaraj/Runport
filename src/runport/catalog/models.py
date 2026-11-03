"""Model metadata specification."""

from decimal import Decimal
from typing import Optional
from pydantic import BaseModel, Field


class ModelCandidate(BaseModel):
    """Metadata specification for an evaluation model candidate."""

    model_id: str = Field(description="Unique provider model identifier (e.g. 'qwen/qwen-2.5-7b-instruct')")
    display_name: str = Field(description="Human-readable model name")
    provider: str = Field(description="Upstream model vendor or aggregator")
    deployment_mode: str = Field(description="HOSTED_OPENROUTER, HOSTED_DIRECT, or SELF_HOSTED_VLLM")
    license: str = Field(description="License type (e.g. Apache-2.0, Meta-Llama, Proprietary)")
    context_length: Optional[int] = Field(default=None, description="Max token context window")
    input_price_per_1m_usd: Decimal = Field(description="Estimated cost per 1M input tokens")
    output_price_per_1m_usd: Decimal = Field(description="Estimated cost per 1M output tokens")
    verification_status: str = Field(
        default="UNVERIFIED_CATALOG_ENTRY",
        description="Verification state against live provider API catalog",
    )
    experimental_purpose: str = Field(default="", description="Role and rationale for inclusion in research workbench")

"""Model portfolio registry and candidate model metadata."""

from decimal import Decimal
from typing import List, Optional
from pydantic import BaseModel, Field

from runport.storage.db import DatabaseManager


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


DEFAULT_PORTFOLIO: List[ModelCandidate] = [
    ModelCandidate(
        model_id="google/gemini-3.5-flash-lite",
        display_name="Gemini 3.5 Flash Lite",
        provider="google",
        deployment_mode="HOSTED_DIRECT",
        license="Proprietary Commercial API",
        context_length=1000000,
        input_price_per_1m_usd=Decimal("0.0750"),
        output_price_per_1m_usd=Decimal("0.3000"),
        verification_status="UNVERIFIED_CATALOG_ENTRY",
        experimental_purpose="High-throughput multimodal baseline for evaluation tasks.",
    ),
    ModelCandidate(
        model_id="anthropic/claude-haiku-5.5",
        display_name="Claude Haiku 5.5",
        provider="anthropic",
        deployment_mode="HOSTED_OPENROUTER",
        license="Proprietary Commercial API",
        context_length=200000,
        input_price_per_1m_usd=Decimal("0.8000"),
        output_price_per_1m_usd=Decimal("4.0000"),
        verification_status="UNVERIFIED_CATALOG_ENTRY",
        experimental_purpose="Fast hosted candidate for benchmarking.",
    ),
    ModelCandidate(
        model_id="openai/gpt-4o-mini",
        display_name="GPT-4o Mini",
        provider="openai",
        deployment_mode="HOSTED_OPENROUTER",
        license="Proprietary Commercial API",
        context_length=128000,
        input_price_per_1m_usd=Decimal("0.1500"),
        output_price_per_1m_usd=Decimal("0.6000"),
        verification_status="UNVERIFIED_CATALOG_ENTRY",
        experimental_purpose="Low-cost reference candidate.",
    ),
    ModelCandidate(
        model_id="openai/gpt-4.1-nano",
        display_name="GPT-4.1 Nano",
        provider="openai",
        deployment_mode="HOSTED_OPENROUTER",
        license="Proprietary Commercial API",
        context_length=128000,
        input_price_per_1m_usd=Decimal("0.1000"),
        output_price_per_1m_usd=Decimal("0.4000"),
        verification_status="UNVERIFIED_CATALOG_ENTRY",
        experimental_purpose="Ultra-compact candidate for fast evaluations.",
    ),
    ModelCandidate(
        model_id="qwen/qwen3-8b",
        display_name="Qwen3-8B",
        provider="qwen",
        deployment_mode="HOSTED_OPENROUTER",
        license="Open-Weight",
        context_length=32768,
        input_price_per_1m_usd=Decimal("0.2000"),
        output_price_per_1m_usd=Decimal("0.2000"),
        verification_status="UNVERIFIED_CATALOG_ENTRY",
        experimental_purpose="Primary open-weight candidate for self-hosted serving.",
    ),
    ModelCandidate(
        model_id="deepseek/deepseek-v4.1-flash",
        display_name="DeepSeek V4.1 Flash",
        provider="deepseek",
        deployment_mode="HOSTED_OPENROUTER",
        license="Proprietary Commercial API",
        context_length=1048576,
        input_price_per_1m_usd=Decimal("0.0490"),
        output_price_per_1m_usd=Decimal("0.3750"),
        verification_status="UNVERIFIED_CATALOG_ENTRY",
        experimental_purpose="High-throughput open weight flash candidate.",
    ),
]


def seed_default_portfolio(db: Optional[DatabaseManager] = None) -> None:
    """Seeds default initial model portfolio into SQLite registry idempotently."""
    db_mgr = db or DatabaseManager()
    db_mgr.init_db()
    for candidate in DEFAULT_PORTFOLIO:
        db_mgr.upsert_model(
            model_id=candidate.model_id,
            display_name=candidate.display_name,
            provider=candidate.provider,
            deployment_mode=candidate.deployment_mode,
            license_type=candidate.license,
            context_length=candidate.context_length,
            input_price_per_1m_usd=f"{candidate.input_price_per_1m_usd:.4f}",
            output_price_per_1m_usd=f"{candidate.output_price_per_1m_usd:.4f}",
            verification_status=candidate.verification_status,
            experimental_purpose=candidate.experimental_purpose,
        )


def get_portfolio(db: Optional[DatabaseManager] = None) -> List[ModelCandidate]:
    """Retrieves all registered models from the local database."""
    db_mgr = db or DatabaseManager()
    db_mgr.init_db()
    rows = db_mgr.get_all_models()
    if not rows:
        seed_default_portfolio(db_mgr)
        rows = db_mgr.get_all_models()

    candidates = []
    for r in rows:
        candidates.append(
            ModelCandidate(
                model_id=r["model_id"],
                display_name=r["display_name"],
                provider=r["provider"],
                deployment_mode=r["deployment_mode"],
                license=r["license"],
                context_length=r["context_length"],
                input_price_per_1m_usd=Decimal(r["input_price_per_1m_usd"]),
                output_price_per_1m_usd=Decimal(r["output_price_per_1m_usd"]),
                verification_status=r["verification_status"],
                experimental_purpose=r.get("experimental_purpose", ""),
            )
        )
    return candidates

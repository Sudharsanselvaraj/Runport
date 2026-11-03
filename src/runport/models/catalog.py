"""Model portfolio registry and candidate model metadata."""

from decimal import Decimal
from pathlib import Path
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


DEFAULT_PORTFOLIO: List[ModelCandidate] = []


def seed_default_portfolio(db: Optional[DatabaseManager] = None, candidates: Optional[List[ModelCandidate]] = None) -> None:
    """Seeds model portfolio into SQLite registry idempotently."""
    db_mgr = db or DatabaseManager()
    db_mgr.init_db()
    items = candidates if candidates is not None else DEFAULT_PORTFOLIO
    for candidate in items:
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


def load_catalog_file(path: Path) -> List[ModelCandidate]:
    """Load model candidates from a JSON or YAML file."""
    import json
    from pathlib import Path
    p = Path(path)
    if not p.is_file():
        return []
    content = p.read_text(encoding="utf-8")
    try:
        data = json.loads(content)
    except json.JSONDecodeError:
        try:
            import yaml  # type: ignore
            data = yaml.safe_load(content)
        except ImportError:
            return []
    if isinstance(data, dict) and "models" in data:
        data = data["models"]
    if not isinstance(data, list):
        return []
    return [ModelCandidate.model_validate(item) for item in data]


def load_catalog_sources(
    sources: List[str],
    db: Optional[DatabaseManager] = None,
) -> List[ModelCandidate]:
    """Load and register candidates from multiple catalog sources (files, paths, or entry-points)."""
    from pathlib import Path
    loaded: List[ModelCandidate] = []
    for src in sources:
        p = Path(src)
        if p.is_file():
            loaded.extend(load_catalog_file(p))
    if loaded and db is not None:
        seed_default_portfolio(db, loaded)
    return loaded


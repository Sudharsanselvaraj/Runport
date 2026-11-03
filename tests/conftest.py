"""Pytest fixtures for runport test suite."""

import pytest
from pathlib import Path


@pytest.fixture
def tmp_kb_dir(tmp_path: Path) -> Path:
    """Provides a temporary directory for isolated KB test fixtures."""
    kb_dir = tmp_path / "kbs"
    kb_dir.mkdir(parents=True, exist_ok=True)
    return kb_dir


@pytest.fixture(autouse=True)
def _isolate_local_state(tmp_path_factory, monkeypatch):
    """Tests never read or write the real ledger/database under data/: point the settings at a private temp location."""
    from runport.core.config import settings

    base = tmp_path_factory.mktemp("isolated_state")
    monkeypatch.setattr(settings, "data_dir", base / "data")
    monkeypatch.setattr(settings, "reports_dir", base / "reports")
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.setenv("RUNPORT_SKIP_DOTENV", "1")

    from decimal import Decimal
    from runport.models.catalog import ModelCandidate, seed_default_portfolio
    from runport.storage.db import DatabaseManager

    settings.ensure_directories()
    db = DatabaseManager(settings.db_path)
    test_models = [
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
            experimental_purpose="High-throughput multimodal baseline for evaluation triage.",
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
            experimental_purpose="Fast candidate for evaluation comparison.",
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
            experimental_purpose="Compact commercial frontier candidate.",
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
            experimental_purpose="Lightweight low-cost reference model.",
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
    ]
    seed_default_portfolio(db, test_models)

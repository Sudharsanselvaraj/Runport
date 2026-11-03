"""Model catalog registry and verification status API endpoints."""

from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Query
from pydantic import BaseModel

from runport.models.catalog import get_portfolio
from runport.storage.db import DatabaseManager
from runport.core.config import settings

router = APIRouter(prefix="/models", tags=["models"])


class ModelCatalogItem(BaseModel):
    model_id: str
    display_name: str
    provider: str
    deployment_mode: str
    license: str
    context_length: Optional[int] = None
    input_price_per_1m_usd: float
    output_price_per_1m_usd: float
    verification_status: str
    experimental_purpose: str = ""


@router.get("", response_model=List[ModelCatalogItem])
def list_catalog_models(
    provider: Optional[str] = Query(None, description="Filter by provider vendor"),
    verified_only: bool = Query(False, description="Filter to primary verified models only"),
    max_input_price: Optional[float] = Query(None, description="Maximum input price per 1M tokens"),
) -> List[ModelCatalogItem]:
    """Returns candidate models from the registry with verified pricing and context limits."""
    settings.ensure_directories()
    db = DatabaseManager(settings.db_path)
    db.init_db()

    models = get_portfolio(db=db)
    results = []

    for m in models:
        if provider and provider.lower() not in m.provider.lower():
            continue
        if verified_only and "VERIFIED" not in m.verification_status:
            continue
        if max_input_price is not None and float(m.input_price_per_1m_usd) > max_input_price:
            continue

        results.append(ModelCatalogItem(
            model_id=m.model_id,
            display_name=m.display_name,
            provider=m.provider,
            deployment_mode=m.deployment_mode,
            license=m.license,
            context_length=m.context_length,
            input_price_per_1m_usd=float(m.input_price_per_1m_usd),
            output_price_per_1m_usd=float(m.output_price_per_1m_usd),
            verification_status=m.verification_status,
            experimental_purpose=m.experimental_purpose,
        ))

    return results


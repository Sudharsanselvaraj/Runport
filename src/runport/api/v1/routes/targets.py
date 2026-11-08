"""Targets and catalog models endpoints for REST API v1.

Specification: docs/SDK_API_CONTRACT.md section 2.2.
"""

from typing import Any, Dict, List
from fastapi import APIRouter, Depends

from runport.api.v1.auth import SCOPE_TARGETS_READ, require_scope
from runport.api.v1.errors import NotFoundError
from runport.api.v1.schemas import TargetItem
from runport.core.workspace import load_workspace_config
from runport.models.catalog import get_portfolio

router = APIRouter(prefix="/targets", tags=["targets"])


@router.get("", response_model=List[TargetItem])
def list_targets(auth: Dict[str, Any] = Depends(require_scope(SCOPE_TARGETS_READ))) -> List[TargetItem]:
    """Returns available benchmark targets across catalog models and workspace connectors."""
    targets: List[TargetItem] = []

    # 1. Catalog models
    for m in get_portfolio():
        targets.append(
            TargetItem(
                target_id=m.model_id,
                name=m.display_name,
                target_type="model",
                provider=m.provider,
                license=m.license,
                context_length=m.context_length,
                input_price_per_1m_usd=float(m.input_price_per_1m_usd),
                output_price_per_1m_usd=float(m.output_price_per_1m_usd),
                verification_status=m.verification_status,
                billing="metered",
            )
        )

    # 2. Workspace target definitions
    ws = load_workspace_config()
    for t in ws.targets:
        targets.append(
            TargetItem(
                target_id=t.id,
                name=t.id,
                target_type=t.type,
                provider=t.type,
                billing=t.billing_mode.value if hasattr(t, "billing_mode") else "metered",
            )
        )

    return targets


@router.get("/{target_id:path}", response_model=TargetItem)
def get_target(target_id: str, auth: Dict[str, Any] = Depends(require_scope(SCOPE_TARGETS_READ))) -> TargetItem:
    """Retrieves target specification by target ID."""
    all_targets = list_targets(auth=auth)
    for t in all_targets:
        if t.target_id == target_id:
            return t
    raise NotFoundError(f"Target '{target_id}' not found.")

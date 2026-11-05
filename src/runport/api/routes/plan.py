"""Live benchmark planning: a fingerprinted, costed plan stored as PENDING until a person approves it."""

from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from runport.connectors.registry import TargetSpecError
from runport.core.config import settings
from runport.services.execution import ExecutionService, load_dataset_cases

router = APIRouter(prefix="/plan", tags=["plan"])


class PlanRequest(BaseModel):
    target_ids: List[str] = Field(min_length=1)
    dataset_name: str
    sample_size: Optional[int] = None
    is_pilot: bool = True


def dataset_path_for(name: str) -> Path:
    d_dir = (settings.workspace_root / "data" / "evaluation").resolve()
    path = (d_dir / name).resolve()
    if d_dir not in path.parents:
        raise HTTPException(status_code=400, detail="Dataset name must refer to a file inside data/evaluation.")
    if not path.is_file():
        raise HTTPException(status_code=404, detail=f"Dataset '{name}' not found")
    return path


@router.post("", response_model=Dict[str, Any])
def create_plan(req: PlanRequest) -> Dict[str, Any]:
    """Creates a live plan. Nothing is sent; the plan must be approved (POST /api/runs/approve) and then executed."""
    cases = load_dataset_cases(dataset_path_for(req.dataset_name), req.sample_size)
    if not cases:
        raise HTTPException(status_code=400, detail="Dataset has 0 valid evaluation cases")
    service = ExecutionService()
    try:
        targets, specs = service.resolve(req.target_ids)
    except (TargetSpecError, KeyError) as e:
        raise HTTPException(status_code=400, detail=f"Cannot build target: {e}") from e
    plan = service.plan(targets, specs, cases, dataset_label=req.dataset_name, requested_by="web_api")
    return plan.to_dict()

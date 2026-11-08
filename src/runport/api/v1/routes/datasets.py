"""Datasets management endpoints for REST API v1.

Specification: docs/SDK_API_CONTRACT.md section 2.2.
"""

from pathlib import Path
import shutil
from typing import Any, Dict, List
from fastapi import APIRouter, Depends, File, UploadFile

from runport.api.v1.auth import SCOPE_DATASETS_READ, SCOPE_DATASETS_WRITE, require_scope
from runport.api.v1.errors import ConfidentialityViolationApiError, NotFoundError
from runport.api.v1.schemas import DatasetSummaryItem, DatasetUploadResponse
from runport.core.config import settings

router = APIRouter(prefix="/datasets", tags=["datasets"])


def _datasets_dir() -> Path:
    d = (settings.workspace_root / "data" / "evaluation").resolve()
    d.mkdir(parents=True, exist_ok=True)
    return d


@router.get("", response_model=List[DatasetSummaryItem])
def list_datasets(auth: Dict[str, Any] = Depends(require_scope(SCOPE_DATASETS_READ))) -> List[DatasetSummaryItem]:
    """Lists available evaluation datasets in data/evaluation/."""
    d_dir = _datasets_dir()
    results: List[DatasetSummaryItem] = []

    for f in sorted(d_dir.glob("*.jsonl")):
        count = 0
        with open(f, "r", encoding="utf-8") as fh:
            for l in fh:
                if l.strip() and not l.startswith("#"):
                    count += 1
        results.append(
            DatasetSummaryItem(
                filename=f.name,
                path=str(f),
                size_bytes=f.stat().st_size,
                case_count=count,
            )
        )
    return results


@router.get("/{name}", response_model=DatasetSummaryItem)
def get_dataset(name: str, auth: Dict[str, Any] = Depends(require_scope(SCOPE_DATASETS_READ))) -> DatasetSummaryItem:
    """Retrieves metadata for a specific dataset file."""
    f = _datasets_dir() / name
    if not f.is_file():
        raise NotFoundError(f"Dataset '{name}' not found.")

    count = 0
    with open(f, "r", encoding="utf-8") as fh:
        for l in fh:
            if l.strip() and not l.startswith("#"):
                count += 1

    return DatasetSummaryItem(
        filename=f.name,
        path=str(f),
        size_bytes=f.stat().st_size,
        case_count=count,
    )


@router.post("", response_model=DatasetUploadResponse)
async def upload_dataset(
    file: UploadFile = File(...),
    auth: Dict[str, Any] = Depends(require_scope(SCOPE_DATASETS_WRITE)),
) -> DatasetUploadResponse:
    """Uploads and verifies a new benchmark dataset JSONL file."""
    if not file.filename or not file.filename.endswith(".jsonl"):
        raise ConfidentialityViolationApiError("Dataset must have a .jsonl extension.")

    d_dir = _datasets_dir()
    dest = d_dir / Path(file.filename).name

    with open(dest, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    lines = 0
    with open(dest, "r", encoding="utf-8") as fh:
        for l in fh:
            if l.strip() and not l.startswith("#"):
                lines += 1

    return DatasetUploadResponse(
        filename=dest.name,
        size_bytes=dest.stat().st_size,
        case_count=lines,
        message=f"Dataset '{dest.name}' uploaded successfully with {lines} cases.",
    )

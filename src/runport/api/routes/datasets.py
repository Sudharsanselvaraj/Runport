"""Evaluation datasets API endpoints."""

import json
from pathlib import Path
import shutil
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, File, HTTPException, UploadFile
from pydantic import BaseModel, Field

from runport.core.config import settings

router = APIRouter(prefix="/datasets", tags=["datasets"])


class DatasetSummary(BaseModel):
    filename: str
    path: str
    size_bytes: int
    case_count: int


class DatasetDetail(BaseModel):
    filename: str
    total_cases: int
    cases_preview: List[Dict[str, Any]] = Field(default_factory=list)


def _get_datasets_dir() -> Path:
    d = settings.workspace_root / "data" / "evaluation"
    d.mkdir(parents=True, exist_ok=True)
    return d


@router.get("", response_model=List[DatasetSummary])
def list_datasets() -> List[DatasetSummary]:
    """Lists available evaluation datasets in data/evaluation/."""
    d_dir = _get_datasets_dir()
    if not d_dir.exists():
        return []

    results = []
    for f in sorted(d_dir.glob("*.jsonl")):
        lines = 0
        with open(f, "r", encoding="utf-8") as fh:
            for l in fh:
                if l.strip() and not l.startswith("#"):
                    lines += 1
        results.append(
            DatasetSummary(
                filename=f.name,
                path=str(f),
                size_bytes=f.stat().st_size,
                case_count=lines,
            )
        )
    return results


@router.post("/upload", response_model=DatasetSummary)
async def upload_dataset(file: UploadFile = File(...)) -> DatasetSummary:
    """Path-traversal-safe dataset upload endpoint."""
    if not file.filename:
        raise HTTPException(status_code=400, detail="Missing filename in upload payload.")

    raw_filename = file.filename or ""
    if ".." in raw_filename or "/" in raw_filename or "\\" in raw_filename:
        raise HTTPException(status_code=400, detail="Path traversal characters detected in filename.")

    # Prevent directory traversal: extract pure basename
    clean_name = Path(raw_filename).name

    if not clean_name.endswith((".jsonl", ".csv", ".json")):
        raise HTTPException(status_code=400, detail="Only .jsonl, .csv, and .json evaluation datasets are permitted.")

    d_dir = _get_datasets_dir().resolve()
    dest_path = (d_dir / clean_name).resolve()

    # Verify destination is strictly inside data/evaluation
    if not str(dest_path).startswith(str(d_dir)):
        raise HTTPException(status_code=400, detail="Path traversal security violation.")

    try:
        with dest_path.open("wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save uploaded dataset: {e}")

    lines = 0
    with dest_path.open("r", encoding="utf-8", errors="replace") as fh:
        for l in fh:
            if l.strip() and not l.startswith("#"):
                lines += 1

    return DatasetSummary(
        filename=dest_path.name,
        path=str(dest_path),
        size_bytes=dest_path.stat().st_size,
        case_count=lines,
    )


@router.get("/{filename}", response_model=DatasetDetail)
def get_dataset(filename: str) -> DatasetDetail:
    """Retrieves metadata and sample cases for a dataset."""
    d_dir = _get_datasets_dir().resolve()
    clean_name = Path(filename).name
    target_file = (d_dir / clean_name).resolve()

    # Safety: ensure path is strictly within data/evaluation
    if not str(target_file).startswith(str(d_dir)):
        raise HTTPException(status_code=400, detail="Path traversal attempt blocked.")
    if not target_file.exists():
        raise HTTPException(status_code=404, detail=f"Dataset '{filename}' not found")

    cases = []
    with open(target_file, "r", encoding="utf-8") as fh:
        for idx, l in enumerate(fh):
            clean = l.strip()
            if not clean or clean.startswith("#"):
                continue
            try:
                cases.append(json.loads(clean))
            except Exception:
                continue

    return DatasetDetail(
        filename=target_file.name,
        total_cases=len(cases),
        cases_preview=cases[:20],
    )

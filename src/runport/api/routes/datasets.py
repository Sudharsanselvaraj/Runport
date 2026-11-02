"""Evaluation datasets API endpoints."""

import json
from pathlib import Path
from typing import Any, Dict, List
from fastapi import APIRouter, HTTPException

from runport.core.config import settings

router = APIRouter(prefix="/datasets", tags=["datasets"])


def _get_datasets_dir() -> Path:
    return settings.workspace_root / "data" / "evaluation"


@router.get("", response_model=List[Dict[str, Any]])
def list_datasets() -> List[Dict[str, Any]]:
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
        results.append({
            "filename": f.name,
            "path": str(f),
            "size_bytes": f.stat().st_size,
            "case_count": lines,
        })
    return results


@router.get("/{filename}", response_model=Dict[str, Any])
def get_dataset(filename: str) -> Dict[str, Any]:
    """Retrieves metadata and sample cases for a dataset."""
    d_dir = _get_datasets_dir()
    target_file = (d_dir / filename).resolve()
    # Safety: ensure path is within data/evaluation
    if not str(target_file).startswith(str(d_dir.resolve())):
        raise HTTPException(status_code=400, detail="Invalid dataset path")
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

    return {
        "filename": target_file.name,
        "total_cases": len(cases),
        "cases_preview": cases[:20],
    }


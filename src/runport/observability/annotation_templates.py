"""Annotation templates for ground-truth verification."""

from pathlib import Path
from typing import Dict, List, Optional, Sequence

ANNOTATION_COLUMNS = [
    "case_id",
    "row_ref",
    "split",
    "category",
    "reviewer_1_id",
    "reviewer_1_label",
    "reviewer_2_id",
    "reviewer_2_label",
    "adjudicated_label",
    "final_expected_label",
    "approval_status",
    "approver_id",
    "approved_date",
    "notes",
]


def write_template(case_ids: Sequence[str], out_path: Path) -> Path:
    """Creates a blank annotation review template. Never overwrites an existing file."""
    out_path = Path(out_path)
    if out_path.exists():
        raise ValueError(f"Template path '{out_path}' already exists; will not overwrite.")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as f:
        f.write(",".join(ANNOTATION_COLUMNS) + "\n")
        for cid in case_ids:
            row = [cid, "", "TEST", "general", "", "", "", "", "", "", "NOT_REVIEWED", "", "", ""]
            f.write(",".join(row) + "\n")
    return out_path

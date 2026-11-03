"""Approved ground-truth labels, read-only.

Labels live in `<dir>/annotations/approved_labels.jsonl`.
This module only READS it, never creates, rewrites or deletes anything there.
A row counts only when its status is APPROVED and it names an approver; a LATER row for the same
case with any other status (for example REVOKED) withdraws the approval.
Predictions, suggested labels and historical model answers are never labels.
"""

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Optional

ANNOTATIONS_DIRNAME = "annotations"
LABELS_FILENAME = "approved_labels.jsonl"
PENDING = "GROUND TRUTH PENDING"


@dataclass
class ApprovedLabels:
    source: Optional[Path] = None
    labels: Dict[str, str] = field(default_factory=dict)
    binary_labels: Dict[str, bool] = field(default_factory=dict)
    n_rows: int = 0
    n_not_approved: int = 0
    n_malformed: int = 0

    @property
    def n_approved(self) -> int:
        return len(self.labels) + len(self.binary_labels)

    @property
    def available(self) -> bool:
        return self.n_approved > 0

    @property
    def status(self) -> str:
        return "APPROVED LABELS PRESENT" if self.available else PENDING

    @property
    def multiclass(self) -> Dict[str, str]:
        return self.labels

    @property
    def binary(self) -> Dict[str, bool]:
        return self.binary_labels


def labels_path(prep_dir: Path) -> Path:
    return Path(prep_dir) / ANNOTATIONS_DIRNAME / LABELS_FILENAME


def load_approved_labels(prep_dir: Optional[Path]) -> ApprovedLabels:
    out = ApprovedLabels()
    if prep_dir is None:
        return out
    path = labels_path(prep_dir) if not Path(prep_dir).is_file() else Path(prep_dir)
    if not path.exists():
        return out
    out.source = path
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        out.n_rows += 1
        try:
            d = json.loads(line)
            cid = str(d.get("case_id"))
            if d.get("status") != "APPROVED" or not str(d.get("approved_by") or "").strip():
                out.n_not_approved += 1
                out.labels.pop(cid, None)
                out.binary_labels.pop(cid, None)
                continue

            exp = d.get("expected")
            if isinstance(exp, bool):
                out.binary_labels[cid] = exp
            elif exp is not None:
                out.labels[cid] = str(exp)
            else:
                out.n_malformed += 1
        except Exception:
            out.n_malformed += 1
    return out

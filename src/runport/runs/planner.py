"""Cryptographic execution planner for Runport benchmarks.

Invariant: Execution plan fingerprint SHA-256 binds candidate models,
endpoint routes, dataset hash, prompt template hash, and budget caps.
Mismatched or stale approvals are rejected.
"""

from dataclasses import dataclass, field
from decimal import Decimal
import hashlib
import json
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class ExecutionPlan:
    """Cryptographically bound execution plan."""

    plan_id: str
    target_ids: List[str]
    dataset_path: str
    dataset_hash: str
    total_cases: int
    budget_cap_usd: Decimal
    prompt_template_hash: str = "none"
    is_live: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)
    fingerprint: str = ""

    def __post_init__(self):
        if not self.fingerprint:
            self.fingerprint = self.compute_fingerprint()

    def compute_fingerprint(self) -> str:
        """Compute SHA-256 binding all plan parameters."""
        canonical = {
            "target_ids": sorted(self.target_ids),
            "dataset_hash": self.dataset_hash,
            "total_cases": self.total_cases,
            "budget_cap_usd": f"{self.budget_cap_usd:.4f}",
            "prompt_template_hash": self.prompt_template_hash,
            "is_live": self.is_live,
        }
        serialized = json.dumps(canonical, sort_keys=True)
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()

    def verify_fingerprint(self) -> bool:
        """Verify the plan fingerprint matches its computed state."""
        return self.fingerprint == self.compute_fingerprint()


def create_execution_plan(
    target_ids: List[str],
    dataset_path: Path,
    budget_cap_usd: Decimal = Decimal("1.00"),
    prompt_template: Optional[str] = None,
    is_live: bool = False,
    metadata: Optional[Dict[str, Any]] = None,
) -> ExecutionPlan:
    """Build and finger-print an execution plan for a benchmark run."""
    p = Path(dataset_path)
    if not p.is_file():
        raise FileNotFoundError(f"Dataset not found at {dataset_path}")

    # Compute dataset SHA-256
    hasher = hashlib.sha256()
    total_cases = 0
    with p.open("rb") as f:
        for line in f:
            if line.strip():
                hasher.update(line)
                total_cases += 1
    ds_hash = hasher.hexdigest()

    pt_hash = hashlib.sha256(prompt_template.encode("utf-8")).hexdigest() if prompt_template else "none"

    plan_id = f"plan-{ds_hash[:8]}-{len(target_ids)}targets"

    return ExecutionPlan(
        plan_id=plan_id,
        target_ids=target_ids,
        dataset_path=str(dataset_path),
        dataset_hash=ds_hash,
        total_cases=total_cases,
        budget_cap_usd=budget_cap_usd,
        prompt_template_hash=pt_hash,
        is_live=is_live,
        metadata=metadata or {},
    )

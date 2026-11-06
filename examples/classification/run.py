#!/usr/bin/env python3
"""Single-label classification benchmark example (offline & deterministic)."""

import json
from pathlib import Path
from runport.runs.executor import GenericRunner
from runport.runs.planner import create_execution_plan
from runport.scorers.stats import prf, wilson
from runport.storage.db import DatabaseManager
from runport.targets.base import BillingMode, CostBasis, Target, TargetResult, TargetStatus, TargetType


class RuleBasedSupportClassifier(Target):
    """Deterministic synthetic target classifying support tickets."""

    def __init__(self) -> None:
        super().__init__(
            target_id="support-classifier",
            name="Rule-Based Ticket Classifier",
            target_type=TargetType.PYTHON_CALLABLE,
            billing=BillingMode.LOCAL,  # runs in-process; nothing leaves this machine
        )

    def execute(self, input_data: dict) -> TargetResult:
        query = str(input_data.get("query", "")).lower()
        if any(w in query for w in ["password", "session", "hijack", "account"]):
            label = "ACCOUNT_SECURITY"
        elif any(w in query for w in ["refund", "charge", "billing", "address"]):
            label = "BILLING"
        else:
            label = "TECHNICAL_SUPPORT"

        return TargetResult(
            target_id=self.target_id,
            status=TargetStatus.SUCCESS,
            output_text=label,
            tokens_in=len(query.split()),
            tokens_out=1,
            cost_basis=CostBasis.UNAVAILABLE,
        )


def main():
    ds_path = Path(__file__).parent / "synthetic_data.jsonl"
    cases = [json.loads(line) for line in ds_path.read_text(encoding="utf-8").splitlines() if line.strip()]

    target = RuleBasedSupportClassifier()
    import os
    import tempfile

    tmp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp_db.close()
    db = DatabaseManager(tmp_db.name)
    db.init_db()
    runner = GenericRunner(db=db)
    plan = create_execution_plan([target.target_id], ds_path, is_live=False)

    results = runner.execute_plan(plan, {target.target_id: target}, cases)
    case_results = results[0].case_results

    correct = 0
    for case, res in zip(cases, case_results):
        is_match = res.output_text == case["ground_truth"]
        if is_match:
            correct += 1
        print(f"[{case['id']}] Expected: {case['ground_truth']} | Got: {res.output_text} | Match: {is_match}")

    acc = correct / len(cases)
    lo, hi = wilson(correct, len(cases))
    print(f"\nAccuracy: {acc:.2%} (Wilson 95% CI: [{lo:.2%}, {hi:.2%}])")
    try:
        os.unlink(tmp_db.name)
    except OSError:
        pass


if __name__ == "__main__":
    main()

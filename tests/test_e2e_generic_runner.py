"""End-to-end offline integration test for GenericRunner.

Covers the full pipeline:
Plan -> Cryptographic Fingerprint -> Token Approval -> Guarded Execution -> Scoring -> Reporting across TWO distinct targets.
Runs completely offline with blocked network sockets.
"""

from decimal import Decimal
import json
from pathlib import Path
import pytest

from runport.connectors.python_target import PythonCallableTarget
from runport.core.approvers import TokenApprover
from runport.core.budget import BudgetService
from runport.core.workspace import BudgetConfig, WorkspaceConfig
from runport.runs.executor import GenericRunner
from runport.runs.planner import ExecutionPlan, create_execution_plan
from runport.scorers import ClassificationReportScorer, CostPer1kScorer, LatencyP95Scorer
from runport.storage.db import DatabaseManager
from runport.targets.base import CostBasis, Target, TargetPricing, TargetResult, TargetStatus, TargetType


class MockEvaluatedTarget(Target):
    """Target simulating a fast candidate model with explicit token and cost telemetry."""

    def __init__(self, target_id: str = "mock-model-a"):
        super().__init__(
            target_id=target_id,
            name="Mock Model A",
            target_type=TargetType.RAW_MODEL,
            pricing=TargetPricing(
                input_usd_per_1m=Decimal("0.20"),
                output_usd_per_1m=Decimal("0.80"),
            ),
        )

    def execute(self, input_payload, context=None):
        query = str(input_payload.get("input") or input_payload.get("query") or "")
        # Deterministic logic
        label = "SPAM" if "free" in query.lower() or "win" in query.lower() else "HAM"
        return TargetResult(
            target_id=self.target_id,
            status=TargetStatus.SUCCESS,
            output_text=label,
            latency_ms=35.0,
            tokens_in=100,
            tokens_out=10,
            cost_usd=Decimal("0.000028"),
            cost_basis=CostBasis.ESTIMATED,
            provenance="LIVE",
        )


def _python_rule_target(payload):
    """Python target evaluating rule-based classification."""
    text = str(payload.get("input") or "").lower()
    return "SPAM" if "winner" in text or "prize" in text else "HAM"


def test_e2e_generic_runner_full_lifecycle(tmp_path):
    """E2E Test: plan -> fingerprint -> approve -> execute -> score -> report for two targets."""
    # 1. Setup workspace and database
    db_path = tmp_path / "e2e_runport.db"
    db = DatabaseManager(db_path)
    db.init_db()

    ws = WorkspaceConfig(
        name="e2e-benchmarking",
        budget=BudgetConfig(
            total_usd=Decimal("10.00"),
            per_run_usd=Decimal("2.00"),
            per_case_usd=Decimal("0.05"),
            pilot_usd=Decimal("2.00"),
            require_priced=False,
        ),
    )
    budget_svc = BudgetService(db=db, policy=ws.budget.to_budget_policy())

    # 2. Create synthetic dataset file
    dataset_file = tmp_path / "dataset.jsonl"
    cases = [
        {"id": "case-1", "classification": "SYNTHETIC", "input": "Claim your free prize today!", "expected": "SPAM"},
        {"id": "case-2", "classification": "SYNTHETIC", "input": "Hello team, let's meet tomorrow at 10am.", "expected": "HAM"},
        {"id": "case-3", "classification": "SYNTHETIC", "input": "You are our lucky winner!", "expected": "SPAM"},
        {"id": "case-4", "classification": "SYNTHETIC", "input": "Weekly project update and slide deck.", "expected": "HAM"},
    ]
    with dataset_file.open("w", encoding="utf-8") as f:
        for c in cases:
            f.write(json.dumps(c) + "\n")

    # 3. Create Execution Plan and Fingerprint
    targets_map = {
        "candidate-model-a": MockEvaluatedTarget("candidate-model-a"),
        "rule-based-engine": PythonCallableTarget(
            target_id="rule-based-engine",
            name="Rule Based Engine",
            func=_python_rule_target,
        ),
    }
    target_ids = list(targets_map.keys())

    plan = create_execution_plan(
        target_ids=target_ids,
        dataset_path=dataset_file,
        budget_cap_usd=Decimal("1.00"),
        prompt_template="{input}",
        is_live=True,
    )

    assert plan.fingerprint is not None
    assert len(plan.fingerprint) == 64
    assert plan.verify_fingerprint() is True

    # 4. Cryptographic Plan Approval via TokenApprover
    approver = TokenApprover(token=plan.fingerprint, enabled=True)

    # 5. Execute Plan via GenericRunner (guarded 7-stage order)
    runner = GenericRunner(budget_service=budget_svc, db=db, workspace=ws)
    run_summaries = runner.execute_plan(
        plan=plan,
        targets=targets_map,
        cases=cases,
        approver=approver,
    )

    assert len(run_summaries) == 2  # Two targets evaluated

    # 6. Score Each Target Output
    scorer = ClassificationReportScorer(allowed_labels=["SPAM", "HAM"])
    lat_scorer = LatencyP95Scorer(threshold_ms=100.0)
    cost_scorer = CostPer1kScorer()

    for summary in run_summaries:
        assert summary.total_cases == 4
        assert summary.successful_cases == 4
        assert summary.invalid_cases == 0

        preds = [r.output_text for r in summary.case_results]
        truths = [c["expected"] for c in cases]

        report = scorer.compute_report(preds, truths)
        assert report.total_cases == 4
        assert report.accuracy >= 0.75  # Both targets perform well on synthetic samples
        assert report.macro_f1 > 0.70

        # Evaluate Latency SLA
        lats = [r.latency_ms for r in summary.case_results if r.latency_ms is not None]
        lat_res = lat_scorer.evaluate_batch(lats)
        assert lat_res.score is not None
        assert lat_res.passed is True

        # Unit economics
        unit_cost_res = cost_scorer.evaluate(summary.total_spend_usd, summary.total_cases)
        assert unit_cost_res.score is not None

    # 7. Verify Persistence and Spend Ledger
    budget_status = budget_svc.get_status()
    assert budget_status.cumulative_spend_usd > Decimal("0.00")
    assert budget_status.unresolved_spend_count == 0  # Clean execution, no unresolved entries

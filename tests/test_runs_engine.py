"""Unit tests for execution planning, fingerprint binding, and generic runner guard order."""

from decimal import Decimal
from pathlib import Path
import pytest

from runport.core.approvers import TokenApprover
from runport.core.budget import BudgetService
from runport.core.workspace import WorkspaceConfig
from runport.providers.base import LiveNotAuthorizedError
from runport.runs.executor import GenericRunner
from runport.runs.planner import create_execution_plan
from runport.storage.db import DatabaseManager
from runport.targets.base import CostBasis, Target, TargetResult, TargetStatus, TargetType


class MockTestTarget(Target):
    def __init__(self, target_id="mock-target", cost=Decimal("0.001")):
        super().__init__(target_id=target_id, name="Mock Target", target_type=TargetType.PYTHON_CALLABLE)
        self.cost = cost
        self.call_count = 0

    def execute(self, payload):
        self.call_count += 1
        return TargetResult(
            target_id=self.target_id,
            status=TargetStatus.SUCCESS,
            output_text="Valid output text",
            cost_usd=self.cost,
            cost_basis=CostBasis.ESTIMATED,
            latency_ms=12.5,
        )


@pytest.fixture
def test_db(tmp_path: Path) -> DatabaseManager:
    db = DatabaseManager(db_path=tmp_path / "test_runs.db")
    db.init_db()
    return db


def test_plan_fingerprint_cryptographic_binding(tmp_path: Path):
    """Plan fingerprint changes when any candidate, dataset, or cap changes."""
    ds_file = tmp_path / "ds.jsonl"
    ds_file.write_text('{"id": "1", "input": "test"}\n', encoding="utf-8")

    plan1 = create_execution_plan(["target-a"], ds_file, budget_cap_usd=Decimal("1.00"))
    plan2 = create_execution_plan(["target-a"], ds_file, budget_cap_usd=Decimal("1.00"))
    assert plan1.fingerprint == plan2.fingerprint
    assert plan1.verify_fingerprint() is True

    # Changed target changes fingerprint
    plan_diff_target = create_execution_plan(["target-b"], ds_file, budget_cap_usd=Decimal("1.00"))
    assert plan_diff_target.fingerprint != plan1.fingerprint

    # Changed budget cap changes fingerprint
    plan_diff_cap = create_execution_plan(["target-a"], ds_file, budget_cap_usd=Decimal("2.00"))
    assert plan_diff_cap.fingerprint != plan1.fingerprint


def test_runner_guard_order_authorization_and_unresolved_spend(tmp_path: Path, test_db: DatabaseManager):
    """Guard 1: Unresolved spend blocks execution; live execution requires valid approval."""
    ds_file = tmp_path / "ds.jsonl"
    ds_file.write_text('{"id": "1", "query": "hello"}\n', encoding="utf-8")

    plan = create_execution_plan(["mock-target"], ds_file, is_live=True)
    target = MockTestTarget()
    budget_svc = BudgetService(db=test_db)
    runner = GenericRunner(budget_service=budget_svc, db=test_db)

    # 1. Blocked if unresolved spend exists on ledger
    test_db.record_transaction(
        transaction_id="tx-unresolved-1",
        model_id="mock-target",
        provider="test",
        amount_usd=Decimal("0.00"),
        description="Unresolved spend test",
        is_unresolved=True,
    )
    with pytest.raises(LiveNotAuthorizedError, match="Unresolved spend detected"):
        runner.execute_plan(plan, {"mock-target": target}, [{"id": "1", "query": "hello"}])

    # Clear unresolved by reconciling
    test_db.reconcile_transaction("tx-unresolved-1", Decimal("0.05"))

    # 2. Blocked if live requested without approver
    with pytest.raises(LiveNotAuthorizedError, match="no approver provided"):
        runner.execute_plan(plan, {"mock-target": target}, [{"id": "1", "query": "hello"}])

    # 3. Blocked if approver token does not match
    bad_approver = TokenApprover(token="wrong-token", enabled=True)
    with pytest.raises(LiveNotAuthorizedError, match="token mismatch"):
        runner.execute_plan(plan, {"mock-target": target}, [{"id": "1", "query": "hello"}], approver=bad_approver)


def test_runner_guard_order_privacy_gate(tmp_path: Path, test_db: DatabaseManager):
    """Guard 2: Whole-batch privacy gate rejects cases with forbidden fields BEFORE transport execution."""
    ds_file = tmp_path / "ds.jsonl"
    ds_file.write_text('{"id": "1", "query": "ok"}\n', encoding="utf-8")

    plan = create_execution_plan(["mock-target"], ds_file, is_live=False)
    target = MockTestTarget()
    runner = GenericRunner(db=test_db)

    cases_with_pii = [
        {"id": "c1", "query": "clean query"},
        {"id": "c2", "query": "clean query", "restricted_user_id": "0123456789"},
    ]

    with pytest.raises(ValueError, match="forbidden field 'restricted_user_id' detected"):
        runner.execute_plan(plan, {"mock-target": target}, cases_with_pii)

    # Invariant: Target was NEVER called because privacy gate ran before transport
    assert target.call_count == 0


def test_runner_offline_execution_and_persistence(tmp_path: Path, test_db: DatabaseManager):
    """Offline execution runs through validation and persists results cleanly."""
    ds_file = tmp_path / "ds.jsonl"
    ds_file.write_text('{"id": "c1", "query": "how are you"}\n', encoding="utf-8")

    plan = create_execution_plan(["mock-target"], ds_file, is_live=False)
    target = MockTestTarget()
    runner = GenericRunner(db=test_db)

    cases = [{"id": "c1", "query": "how are you"}]
    results = runner.execute_plan(plan, {"mock-target": target}, cases)

    assert len(results) == 1
    run_res = results[0]
    assert run_res.successful_cases == 1
    assert run_res.total_cases == 1
    assert target.call_count == 1

    # Verify persisted in DB
    runs = test_db.get_all_evaluation_runs()
    assert any(r["run_id"] == run_res.run_id for r in runs)

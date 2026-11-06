"""Atomic budget reservation: the per-run ceiling is cumulative and concurrent runs cannot jointly exceed a ceiling."""

import threading
import time
from decimal import Decimal

import pytest

from runport.core.approvers import TokenApprover
from runport.core.budget import BudgetExceededError, BudgetService
from runport.core.config import BudgetPolicy
from runport.core.workspace import BudgetConfig, WorkspaceConfig
from runport.runs.executor import GenericRunner
from runport.runs.planner import ExecutionPlan
from runport.storage.db import DatabaseManager
from runport.targets.base import BillingMode, CostBasis, Target, TargetPricing, TargetResult, TargetStatus, TargetType


class Priced(Target):
    """Billable target priced at $0.001 per request; can report a different actual cost."""

    def __init__(self, actual: Decimal = Decimal("0.001"), delay_s: float = 0.0, billing=BillingMode.BILLABLE):
        super().__init__("t", "t", TargetType.WORKFLOW_HTTP, pricing=TargetPricing(fixed_usd_per_request=Decimal("0.001")), billing=billing)
        self.actual = actual
        self.delay_s = delay_s
        self.calls = 0

    def execute(self, input_payload, context=None):
        self.calls += 1
        if self.delay_s:
            time.sleep(self.delay_s)
        return TargetResult("t", TargetStatus.SUCCESS, output_text="ok", cost_usd=self.actual, cost_basis=CostBasis.ESTIMATED)


def _runner(db, total="1.00", per_run="1.00"):
    policy = BudgetPolicy(
        total_budget_usd=Decimal(total), pilot_budget_usd=Decimal(total), per_run_ceiling_usd=Decimal(per_run), per_case_ceiling_usd=Decimal("0.05")
    )
    ws = WorkspaceConfig(budget=BudgetConfig())
    return GenericRunner(budget_service=BudgetService(db=db, policy=policy), db=db, workspace=ws)


def _run(runner, target, n, cap="1.00"):
    plan = ExecutionPlan(plan_id="p", target_ids=["t"], dataset_path="d", dataset_hash="h", total_cases=n, budget_cap_usd=Decimal(cap), is_live=True)
    cases = [{"id": f"c{i}", "classification": "SYNTHETIC", "query": "q"} for i in range(n)]
    return runner.execute_plan(plan, {"t": target}, cases, approver=TokenApprover(plan.fingerprint, enabled=True))[0]


def _booked(db):
    return db.get_cumulative_spend()[1]


def test_per_run_ceiling_is_cumulative(tmp_path):
    db = DatabaseManager(tmp_path / "a.db")
    target = Priced()
    run = _run(_runner(db), target, 5, cap="0.0025")
    assert target.calls == 2 and len(run.case_results) == 2 and run.skipped_cases == 3
    assert run.halt_kind == "budget" and "per-run ceiling" in run.halted_reason
    assert run.total_spend_usd == Decimal("0.002")
    assert db.get_open_reservations()[1] == 0


def test_actual_cost_above_estimate_stops_the_run_after_one_overage(tmp_path):
    db = DatabaseManager(tmp_path / "b.db")
    target = Priced(actual=Decimal("0.002"))  # estimate 0.001, actual 0.002
    run = _run(_runner(db), target, 10, cap="0.003")
    # Case 1: reserve 0.001, book 0.002. Case 2: 0.002 + 0.001 <= 0.003, book 0.002. Case 3: 0.004 + 0.001 > 0.003 -> stop.
    assert target.calls == 2 and run.halt_kind == "budget"
    assert run.total_spend_usd == Decimal("0.004")  # at most one case's overage beyond the cap, never more


def test_first_case_refusal_still_raises(tmp_path):
    db = DatabaseManager(tmp_path / "c.db")
    with pytest.raises(BudgetExceededError, match="per-run ceiling"):
        _run(_runner(db), Priced(), 3, cap="0.0005")


def test_concurrent_runs_cannot_jointly_exceed_the_total_ceiling(tmp_path):
    db = DatabaseManager(tmp_path / "d.db")
    db.init_db()
    targets = [Priced(delay_s=0.02) for _ in range(4)]
    errors = []

    def go(t):
        try:
            _run(_runner(db, total="0.006"), t, 5)
        except BudgetExceededError:
            errors.append(1)

    threads = [threading.Thread(target=go, args=(t,)) for t in targets]
    for th in threads:
        th.start()
    for th in threads:
        th.join()
    assert _booked(db) <= Decimal("0.006")
    assert sum(t.calls for t in targets) <= 6
    assert db.get_open_reservations()[1] == 0


def test_targets_that_cannot_bill_reserve_nothing(tmp_path):
    db = DatabaseManager(tmp_path / "e.db")
    local = Priced(actual=None, billing=BillingMode.LOCAL)
    run = _run(_runner(db, total="0.00", per_run="0.00"), local, 3)
    assert local.calls == 3 and run.halted_reason is None


def test_expired_reservations_do_not_hold_budget(tmp_path):
    db = DatabaseManager(tmp_path / "f.db")
    db.init_db()
    svc = BudgetService(db=db, policy=BudgetPolicy(total_budget_usd=Decimal("0.001"), pilot_budget_usd=Decimal("0.001")))
    assert (
        db.reserve_budget(
            "old", "r0", Decimal("0.001"), is_pilot=True, total_cap_usd=Decimal("1"), pilot_cap_usd=Decimal("1"), run_cap_usd=Decimal("1"), ttl_s=-1
        )
        is None
    )
    rid = svc.reserve("r1", Decimal("0.001"))
    svc.release(rid)
    assert db.get_open_reservations()[1] == 0

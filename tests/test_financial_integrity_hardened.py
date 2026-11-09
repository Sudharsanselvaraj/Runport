"""Comprehensive financial and execution integrity tests for Phase 4.

Verifies:
- 4.1 Budget reservation correctness under sufficiency, insufficiency, concurrency, provider failure, and cancellation.
- 4.2 Idempotency for job submission, spend booking, duplicate completion events, and recovery.
- 4.3 Execution invariants: unapproved/blocked plans cannot execute, replay executions book $0.00 spend.
"""

from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from pathlib import Path
import threading
from typing import Any, Dict
import pytest
from starlette.testclient import TestClient

from runport.api.app import create_app
from runport.api.v1.auth import hash_api_key
from runport.api.v1.jobs import JobManager
from runport.core.approvers import TokenApprover
from runport.core.budget import BudgetExceededError, BudgetService
from runport.core.config import settings
from runport.core.workspace import BudgetConfig, WorkspaceConfig
from runport.runs.executor import GenericRunner
from runport.runs.planner import ExecutionPlan
from runport.services.approvals import ApprovalError, ApprovalStore
from runport.services.execution import ExecutionService
from runport.storage.db import DatabaseManager
from runport.targets.base import (
    BillingMode,
    CostBasis,
    Target,
    TargetPricing,
    TargetResult,
    TargetStatus,
    TargetType,
)


@pytest.fixture
def financial_env(tmp_path: Path, monkeypatch):
    """Sets up an isolated test database and test environment."""
    db_file = tmp_path / "financial_integrity.db"
    monkeypatch.setenv("RUNPORT_DB_PATH", str(db_file))
    monkeypatch.setenv("RUNPORT_API_TOKEN", "master-token-xyz")
    monkeypatch.setattr(type(settings), "db_path", property(lambda self: db_file))

    db = DatabaseManager(db_file)
    db.init_db()

    JobManager._instance = None
    job_mgr = JobManager()

    # Seed organization and project
    with db.get_connection() as conn:
        conn.execute("INSERT OR IGNORE INTO organizations (org_id, name, created_at) VALUES ('org-fin', 'Finance Org', '2026-01-01')")
        conn.execute(
            "INSERT OR IGNORE INTO projects (project_id, org_id, name, settings_json, created_at) VALUES ('proj-fin', 'org-fin', 'Finance Project', '{}', '2026-01-01')"
        )

    raw_key = "rp_live_fin_1234567890abcdef"
    full_scopes = [
        "targets:read",
        "datasets:read",
        "datasets:write",
        "plans:create",
        "plans:approve",
        "runs:execute",
        "runs:read",
        "traces:write",
        "budget:read",
        "budget:reconcile",
    ]
    db.create_api_key(
        key_id="key-fin",
        name="Finance Operator",
        key_hash=hash_api_key(raw_key),
        scopes=full_scopes,
        project_id="proj-fin",
        principal="fin-op@runport.local",
    )

    app = create_app()
    client = TestClient(app)

    return {
        "db": db,
        "job_mgr": job_mgr,
        "client": client,
        "raw_key": raw_key,
        "project_id": "proj-fin",
        "tmp_path": tmp_path,
    }


class BillableMockTarget(Target):
    """Predictable mock target with pricing."""

    def __init__(self, target_id: str = "mock-model", fail_on_case: int = -1):
        super().__init__(
            target_id=target_id,
            name="Mock Billable Model",
            target_type=TargetType.RAW_MODEL,
            billing=BillingMode.BILLABLE,
            pricing=TargetPricing(input_usd_per_1m=Decimal("1.00"), output_usd_per_1m=Decimal("2.00")),
        )
        self.call_count = 0
        self.fail_on_case = fail_on_case

    def execute(self, input_payload: Dict[str, Any], context=None) -> TargetResult:
        self.call_count += 1
        if self.call_count == self.fail_on_case:
            raise RuntimeError("Provider connection reset (500 internal error)")

        return TargetResult(
            target_id=self.target_id,
            status=TargetStatus.SUCCESS,
            output_text="Synthesized completion answer.",
            latency_ms=25.0,
            tokens_in=100,
            tokens_out=50,
            cost_usd=Decimal("0.000200"),
            cost_basis=CostBasis.ACTUAL,
            provenance="LIVE",
        )


def _make_workspace(total_usd: Decimal = Decimal("5.00"), per_run_usd: Decimal = Decimal("2.00")) -> WorkspaceConfig:
    b = BudgetConfig(
        total_usd=total_usd,
        pilot_usd=total_usd,
        per_run_usd=per_run_usd,
        per_case_usd=Decimal("0.05"),
        require_priced=False,
    )
    return WorkspaceConfig(budget=b, targets=[])


def test_budget_sufficient_executes_successfully(financial_env):
    """Sufficient budget permits execution, books spend in ledger, and releases all reservations."""
    db: DatabaseManager = financial_env["db"]
    ws = _make_workspace(total_usd=Decimal("5.00"))
    budget_svc = BudgetService(db=db, policy=ws.budget.to_budget_policy())
    runner = GenericRunner(budget_service=budget_svc, db=db, workspace=ws)

    target = BillableMockTarget("mock-sufficient")
    plan = ExecutionPlan(
        plan_id="plan-suff-001",
        target_ids=[target.target_id],
        dataset_path="",
        dataset_hash="hash-abc",
        total_cases=2,
        budget_cap_usd=Decimal("1.00"),
        prompt_template_hash="tpl-hash",
        is_live=True,
    )
    approver = TokenApprover(token=plan.fingerprint, enabled=True, operator="test-op")
    cases = [
        {"id": "c1", "query": "hello world", "classification": "PUBLIC"},
        {"id": "c2", "query": "second prompt", "classification": "PUBLIC"},
    ]

    results = runner.execute_plan(plan, {target.target_id: target}, cases, approver=approver)

    assert len(results) == 1
    run_res = results[0]
    assert run_res.successful_cases == 2
    assert run_res.failed_cases == 0
    assert run_res.total_spend_usd == Decimal("0.000400")

    # Reservations released
    micros, held = db.get_open_reservations()
    assert micros == 0
    assert held == Decimal("0.00")

    # Booked spend in ledger
    _, spent = db.get_cumulative_spend(include_estimates=False)
    assert spent == Decimal("0.000400")


def test_budget_insufficient_blocks_execution(financial_env):
    """Insufficient budget raises BudgetExceededError fail-closed before transport execution."""
    db: DatabaseManager = financial_env["db"]
    # Total budget only $0.00001 (cannot afford worst case of $0.05 or target cost)
    ws = _make_workspace(total_usd=Decimal("0.00001"))
    budget_svc = BudgetService(db=db, policy=ws.budget.to_budget_policy())
    runner = GenericRunner(budget_service=budget_svc, db=db, workspace=ws)

    target = BillableMockTarget("mock-insufficient")
    plan = ExecutionPlan(
        plan_id="plan-insuff-001",
        target_ids=[target.target_id],
        dataset_path="",
        dataset_hash="hash-insuff",
        total_cases=1,
        budget_cap_usd=Decimal("1.00"),
        prompt_template_hash="tpl-insuff",
        is_live=True,
    )
    approver = TokenApprover(token=plan.fingerprint, enabled=True, operator="test-op")
    cases = [{"id": "c1", "query": "test query", "classification": "PUBLIC"}]

    with pytest.raises(BudgetExceededError) as exc_info:
        runner.execute_plan(plan, {target.target_id: target}, cases, approver=approver)

    assert "ceiling" in str(exc_info.value).lower()
    assert target.call_count == 0  # Transport was never invoked

    # Zero spend booked
    _, spent = db.get_cumulative_spend()
    assert spent == Decimal("0.00")
    micros, _ = db.get_open_reservations()
    assert micros == 0


def test_concurrent_budget_reservations_prevent_overspend(financial_env):
    """Concurrent parallel workers under SQLite WAL mode cannot exceed ceilings."""
    db: DatabaseManager = financial_env["db"]
    # Total budget $0.05
    ws = _make_workspace(total_usd=Decimal("0.05"), per_run_usd=Decimal("0.05"))
    budget_svc = BudgetService(db=db, policy=ws.budget.to_budget_policy())

    successes = []
    failures = []

    def attempt_reservation(worker_num: int):
        # Each worker asks to reserve $0.04
        try:
            rsv_id = budget_svc.reserve(
                run_id=f"run-worker-{worker_num}",
                worst_case_usd=Decimal("0.04"),
                run_cap_usd=Decimal("0.05"),
                is_pilot=True,
            )
            successes.append(rsv_id)
        except BudgetExceededError as e:
            failures.append(str(e))

    # Run two workers in parallel
    with ThreadPoolExecutor(max_workers=2) as executor:
        f1 = executor.submit(attempt_reservation, 1)
        f2 = executor.submit(attempt_reservation, 2)
        f1.result()
        f2.result()

    # Exactly one succeeded and one failed
    assert len(successes) == 1
    assert len(failures) == 1
    assert "total ceiling" in failures[0].lower()

    # Total open reservation is exactly $0.04, not exceeding $0.05
    _, held = db.get_open_reservations()
    assert held == Decimal("0.040000")

    # Clean up
    budget_svc.release(successes[0])
    _, held_after = db.get_open_reservations()
    assert held_after == Decimal("0.00")


def test_provider_failure_releases_reservation(financial_env):
    """When a provider crashes or returns 500, reservation is safely released in try...finally."""
    db: DatabaseManager = financial_env["db"]
    ws = _make_workspace(total_usd=Decimal("1.00"))
    budget_svc = BudgetService(db=db, policy=ws.budget.to_budget_policy())
    runner = GenericRunner(budget_service=budget_svc, db=db, workspace=ws)

    # Fails on case 1
    target = BillableMockTarget("mock-failing-provider", fail_on_case=1)
    plan = ExecutionPlan(
        plan_id="plan-fail-001",
        target_ids=[target.target_id],
        dataset_path="",
        dataset_hash="hash-fail",
        total_cases=1,
        budget_cap_usd=Decimal("1.00"),
        prompt_template_hash="tpl-fail",
        is_live=True,
    )
    approver = TokenApprover(token=plan.fingerprint, enabled=True, operator="test-op")
    cases = [{"id": "c1", "query": "crash me", "classification": "PUBLIC"}]

    results = runner.execute_plan(plan, {target.target_id: target}, cases, approver=approver)

    assert len(results) == 1
    run_res = results[0]
    assert run_res.failed_cases == 1
    assert run_res.successful_cases == 0

    # Crucial: reservation MUST be released despite exception
    micros, held = db.get_open_reservations()
    assert micros == 0
    assert held == Decimal("0.00")


def test_cancellation_settles_actual_spend(financial_env):
    """Cancelled job settles spend for completed cases only, releasing all remaining budget."""
    db: DatabaseManager = financial_env["db"]
    ws = _make_workspace(total_usd=Decimal("5.00"))
    budget_svc = BudgetService(db=db, policy=ws.budget.to_budget_policy())
    runner = GenericRunner(budget_service=budget_svc, db=db, workspace=ws)

    cancel_evt = threading.Event()

    class CancellingTarget(BillableMockTarget):
        def execute(self, input_payload: Dict[str, Any], context=None) -> TargetResult:
            res = super().execute(input_payload, context)
            if self.call_count >= 1:
                cancel_evt.set()  # Cancel after first case
            return res

    target = CancellingTarget("mock-cancel-target")
    plan = ExecutionPlan(
        plan_id="plan-cancel-001",
        target_ids=[target.target_id],
        dataset_path="",
        dataset_hash="hash-cancel",
        total_cases=4,
        budget_cap_usd=Decimal("1.00"),
        prompt_template_hash="tpl-cancel",
        is_live=True,
    )
    approver = TokenApprover(token=plan.fingerprint, enabled=True, operator="test-op")
    cases = [{"id": f"c{i}", "query": f"prompt {i}", "classification": "PUBLIC"} for i in range(1, 5)]

    results = runner.execute_plan(plan, {target.target_id: target}, cases, approver=approver, cancel_token=cancel_evt)

    assert len(results) == 1
    run_res = results[0]
    assert run_res.successful_cases == 1
    assert run_res.skipped_cases == 3
    assert run_res.halt_kind == "cancelled"
    assert run_res.total_spend_usd == Decimal("0.000200")

    # Spend in ledger matches exactly 1 case
    _, spent = db.get_cumulative_spend()
    assert spent == Decimal("0.000200")

    # Zero open reservations
    micros, held = db.get_open_reservations()
    assert micros == 0
    assert held == Decimal("0.00")


def test_duplicate_completion_event_prevention(financial_env):
    """Deterministic transaction IDs prevent double-booking on duplicated completion callbacks."""
    db: DatabaseManager = financial_env["db"]
    ws = _make_workspace()
    budget_svc = BudgetService(db=db, policy=ws.budget.to_budget_policy())

    tx_id = "tx-run-test-c1"

    # First completion event
    booked_first = budget_svc.record_spend(
        transaction_id=tx_id,
        model_id="mock-model",
        provider="test-prov",
        amount_usd=Decimal("0.000500"),
        description="Run test Case c1",
        run_id="run-test",
        is_pilot=True,
        cost_basis="ACTUAL",
    )
    assert booked_first is True

    # Duplicate completion event (e.g. webhook/retry)
    booked_second = budget_svc.record_spend(
        transaction_id=tx_id,
        model_id="mock-model",
        provider="test-prov",
        amount_usd=Decimal("0.000500"),
        description="Run test Case c1 (Duplicate)",
        run_id="run-test",
        is_pilot=True,
        cost_basis="ACTUAL",
    )
    assert booked_second is False  # Safely ignored

    # Ledger has exactly one transaction and single spend amount
    _, spent = db.get_cumulative_spend()
    assert spent == Decimal("0.000500")

    txs = db.get_recent_transactions(limit=10)
    matching = [t for t in txs if t["transaction_id"] == tx_id]
    assert len(matching) == 1


def test_idempotent_job_submission(financial_env):
    """Submitting POST /plans/{plan_id}/runs twice with the same Idempotency-Key returns the existing job."""
    client: TestClient = financial_env["client"]
    raw_key: str = financial_env["raw_key"]
    db: DatabaseManager = financial_env["db"]
    headers = {"Authorization": f"Bearer {raw_key}"}

    # Register approval plan directly
    approvals = ApprovalStore(db=db)
    summary = {
        "nonce": "nonce-idemp-12345",
        "target_ids": ["mock-model"],
        "specs": {"mock-model": {"type": "openrouter", "model": "mock-model"}},
        "case_count": 1,
        "cases_digest": "digest-123",
        "dataset_label": "synthetic_seed_eval.jsonl",
        "projected_max_cost_usd": "0.01",
        "per_target": [{"target_id": "mock-model", "billing": "billable", "priced": True}],
        "blockers": [],
        "source": {},
    }
    rec = approvals.register("fingerprint-idemp-12345", summary, requested_by="operator-1", project_id="proj-fin")
    plan_id = rec.plan_id

    # Approve plan
    approved_rec = approvals.approve(plan_id, "fingerprint-idemp-12345", channel="rest_v1", approver="operator-2", project_id="proj-fin")
    assert approved_rec.status == "APPROVED"

    idempotency_key = "idemp-submit-unique-key-777"

    # Mock JobManager._run_job_worker to avoid spawning threads in unit test
    def noop_worker(*args, **kwargs):
        pass

    financial_env["job_mgr"]._run_job_worker = noop_worker

    # First submission with Idempotency-Key header
    r1 = client.post(
        f"/api/v1/plans/{plan_id}/runs",
        headers={**headers, "Idempotency-Key": idempotency_key},
        json={"sample_size": 1},
    )
    assert r1.status_code == 202
    data1 = r1.json()
    job_id_1 = data1["job_id"]
    assert data1["idempotency_key"] == idempotency_key

    # Second submission with the exact same Idempotency-Key
    r2 = client.post(
        f"/api/v1/plans/{plan_id}/runs",
        headers={**headers, "Idempotency-Key": idempotency_key},
        json={"sample_size": 1},
    )
    assert r2.status_code == 202
    data2 = r2.json()
    assert data2["job_id"] == job_id_1  # Exact same job returned

    # Verify only one job exists in the database
    jobs = db.list_run_jobs(project_id="proj-fin")
    matching_jobs = [j for j in jobs if j.get("idempotency_key") == idempotency_key]
    assert len(matching_jobs) == 1


def test_unapproved_plan_execution_blocked(financial_env):
    """Attempting to execute an unapproved or consumed plan is strictly blocked fail-closed."""
    client: TestClient = financial_env["client"]
    raw_key: str = financial_env["raw_key"]
    db: DatabaseManager = financial_env["db"]
    headers = {"Authorization": f"Bearer {raw_key}"}

    exec_svc = ExecutionService(db=db)
    target = BillableMockTarget("mock-model")
    spec = {"type": "openrouter", "model": "mock-model"}
    cases = [{"id": "c1", "query": "hello"}]

    plan_summary = exec_svc.plan(
        {target.target_id: target},
        {target.target_id: spec},
        cases,
        dataset_label="synthetic_seed_eval.jsonl",
        requested_by="operator-1",
        project_id="proj-fin",
    )
    plan_id = plan_summary.plan_id

    # REST endpoint check
    r = client.post(f"/api/v1/plans/{plan_id}/runs", headers=headers, json={})
    assert r.status_code == 428
    data = r.json()
    msg = data.get("error", {}).get("message", "") or str(data)
    assert "must be approved before execution" in msg.lower()

    # Direct ExecutionService check
    with pytest.raises(ApprovalError) as exc_info:
        exec_svc.execute(
            plan_id=plan_id,
            targets={target.target_id: target},
            specs={target.target_id: spec},
            cases=cases,
        )
    assert "not been approved" in str(exc_info.value).lower()
    assert target.call_count == 0


def test_blocked_plan_execution_blocked(financial_env):
    """Plans with unresolved blockers cannot be approved or submitted for execution."""
    client: TestClient = financial_env["client"]
    raw_key: str = financial_env["raw_key"]
    db: DatabaseManager = financial_env["db"]
    headers = {"Authorization": f"Bearer {raw_key}"}

    approvals = ApprovalStore(db=db)
    summary = {
        "nonce": "nonce-blocked-12345",
        "target_ids": ["mock-model"],
        "specs": {"mock-model": {"type": "openrouter", "model": "mock-model"}},
        "case_count": 1,
        "cases_digest": "digest-blk",
        "dataset_label": "sample_eval.jsonl",
        "projected_max_cost_usd": "0.01",
        "per_target": [{"target_id": "mock-model", "billing": "billable", "priced": True}],
        "blockers": ["Unresolved spend exists; reconcile it before live runs."],
        "source": {},
    }
    rec = approvals.register("fingerprint-blocked-999", summary, requested_by="operator-1", project_id="proj-fin")
    plan_id = rec.plan_id

    # Attempting to approve must fail
    r = client.post(
        f"/api/v1/plans/{plan_id}/approve",
        headers=headers,
        json={"fingerprint": "fingerprint-blocked-999", "approver": "lead-op"},
    )
    assert r.status_code == 409
    data = r.json()
    msg = data.get("error", {}).get("message", "") or str(data)
    assert "preflight blocker" in msg.lower()


def test_replay_execution_zero_spend(financial_env):
    """Replay executions (is_live=False) bypass budget reservations and strictly record $0.00 spend."""
    db: DatabaseManager = financial_env["db"]
    ws = _make_workspace(total_usd=Decimal("5.00"))
    budget_svc = BudgetService(db=db, policy=ws.budget.to_budget_policy())
    runner = GenericRunner(budget_service=budget_svc, db=db, workspace=ws)

    target = BillableMockTarget("mock-replay-target")
    plan = ExecutionPlan(
        plan_id="plan-replay-001",
        target_ids=[target.target_id],
        dataset_path="",
        dataset_hash="hash-replay",
        total_cases=2,
        budget_cap_usd=Decimal("1.00"),
        prompt_template_hash="tpl-replay",
        is_live=False,  # Replay mode
    )
    approver = TokenApprover(token=plan.fingerprint, enabled=True, operator="test-op")
    cases = [
        {"id": "c1", "query": "hello replay", "classification": "PUBLIC"},
        {"id": "c2", "query": "second replay", "classification": "PUBLIC"},
    ]

    results = runner.execute_plan(plan, {target.target_id: target}, cases, approver=approver)

    assert len(results) == 1
    run_res = results[0]
    assert run_res.successful_cases == 2
    # In replay mode, total spend is strictly 0.00
    assert run_res.total_spend_usd == Decimal("0.00")

    # Ledger cumulative live spend is $0.00
    _, live_spent = db.get_cumulative_spend()
    assert live_spent == Decimal("0.00")

    # Open reservations is 0
    micros, held = db.get_open_reservations()
    assert micros == 0
    assert held == Decimal("0.00")

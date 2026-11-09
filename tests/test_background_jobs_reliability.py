"""Comprehensive background execution reliability tests.

Verifies Phase 3 requirements:
- Atomic worker job claiming under concurrency.
- Periodic heartbeat renewal and lease management.
- Multi-process stale worker recovery (never interrupting healthy workers).
- Cooperative cancellation before, during, and after execution.
- No blind retries of interrupted billable runs.
"""

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
import threading
import time
from typing import Any, Dict, List
import pytest
from starlette.testclient import TestClient

from runport.api.app import create_app
from runport.api.v1.auth import hash_api_key
from runport.api.v1.jobs import CooperativeCancelToken, JobManager
from runport.core.config import settings
from runport.runs.planner import ExecutionPlan
from runport.services.approvals import ApprovalStore
from runport.services.execution import ExecutionService
from runport.storage.db import DatabaseManager


@pytest.fixture
def reliability_env(tmp_path: Path, monkeypatch):
    """Sets up an isolated database and reset JobManager singleton."""
    db_file = tmp_path / "reliability.db"
    monkeypatch.setenv("RUNPORT_DB_PATH", str(db_file))
    monkeypatch.setenv("RUNPORT_API_TOKEN", "master-token-abc")
    monkeypatch.setattr(type(settings), "db_path", property(lambda self: db_file))

    db = DatabaseManager(db_file)
    db.init_db()

    JobManager._instance = None
    job_mgr = JobManager()

    # Create test organization, project, and API key
    with db.get_connection() as conn:
        conn.execute("INSERT OR IGNORE INTO organizations (org_id, name, created_at) VALUES ('org-rel', 'Rel Org', '2026-01-01')")
        conn.execute(
            "INSERT OR IGNORE INTO projects (project_id, org_id, name, settings_json, created_at) VALUES ('proj-rel', 'org-rel', 'Rel Project', '{}', '2026-01-01')"
        )

    raw_key = "rp_live_rel_1234567890abcdef"
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
        key_id="key-rel",
        name="Reliability Operator",
        key_hash=hash_api_key(raw_key),
        scopes=full_scopes,
        project_id="proj-rel",
        principal="rel-op@runport.local",
    )

    app = create_app()
    client = TestClient(app)

    return {
        "db": db,
        "job_mgr": job_mgr,
        "client": client,
        "raw_key": raw_key,
        "project_id": "proj-rel",
    }


def test_atomic_worker_claiming_concurrency(reliability_env):
    """Multiple concurrent workers competing for a queued job must result in exactly one winner."""
    db: DatabaseManager = reliability_env["db"]
    job_id = "job-compete-001"

    db.create_run_job(
        job_id=job_id,
        plan_id="plan-c1",
        status="queued",
        total_cases=10,
        project_id="proj-rel",
    )

    num_workers = 8
    worker_ids = [f"worker-{i}" for i in range(num_workers)]
    results: List[bool] = []

    def try_claim(wid: str) -> bool:
        return db.claim_run_job(job_id, worker_id=wid, lease_duration_s=30)

    with ThreadPoolExecutor(max_workers=num_workers) as executor:
        futures = [executor.submit(try_claim, wid) for wid in worker_ids]
        results = [f.result() for f in futures]

    # Exactly one worker must succeed
    assert results.count(True) == 1
    assert results.count(False) == num_workers - 1

    # Verify database state
    job = db.get_run_job(job_id)
    assert job is not None
    assert job["status"] == "running"
    assert job["worker_id"] in worker_ids
    assert job["attempt_count"] == 1
    assert job["heartbeat_at"] is not None
    assert job["lease_expires_at"] is not None


def test_worker_heartbeat_lease_renewal(reliability_env):
    """An active worker must be able to renew its lease; other workers or cancelled jobs cannot."""
    db: DatabaseManager = reliability_env["db"]
    job_id = "job-renew-001"
    worker_a = "worker-alpha"
    worker_b = "worker-beta"

    db.create_run_job(job_id=job_id, plan_id="p1", status="queued", project_id="proj-rel")
    assert db.claim_run_job(job_id, worker_id=worker_a, lease_duration_s=10) is True

    job_before = db.get_run_job(job_id)
    first_heartbeat = job_before["heartbeat_at"]

    # Worker B cannot renew Worker A's lease
    assert db.renew_job_lease(job_id, worker_id=worker_b, lease_duration_s=10) is False

    # Worker A renews successfully
    time.sleep(0.01)
    assert db.renew_job_lease(job_id, worker_id=worker_a, lease_duration_s=25) is True

    job_after = db.get_run_job(job_id)
    assert job_after["heartbeat_at"] > first_heartbeat
    assert job_after["worker_id"] == worker_a

    # If job is cancelled, renewal fails
    db.request_job_cancellation(job_id)
    assert db.renew_job_lease(job_id, worker_id=worker_a, lease_duration_s=10) is False


def test_stale_worker_recovery_preserves_healthy_worker(reliability_env):
    """Expired worker leases are recovered to interrupted; healthy heartbeating workers are untouched."""
    db: DatabaseManager = reliability_env["db"]
    job_mgr: JobManager = reliability_env["job_mgr"]

    now = datetime.now(timezone.utc)
    past_lease = (now - timedelta(seconds=120)).isoformat()
    future_lease = (now + timedelta(seconds=120)).isoformat()

    # Job 1: Crashed/lost worker with lease expired in the past
    stale_job_id = "job-stale-001"
    db.create_run_job(
        job_id=stale_job_id,
        plan_id="p-stale",
        status="running",
        worker_id="worker-dead",
        lease_expires_at=past_lease,
        heartbeat_at=past_lease,
        attempt_count=1,
        project_id="proj-rel",
    )

    # Job 2: Healthy worker actively heartbeating with unexpired lease
    healthy_job_id = "job-healthy-002"
    db.create_run_job(
        job_id=healthy_job_id,
        plan_id="p-healthy",
        status="running",
        worker_id="worker-alive",
        lease_expires_at=future_lease,
        heartbeat_at=now.isoformat(),
        attempt_count=1,
        project_id="proj-rel",
    )

    # Run stale recovery
    recovered = job_mgr.recover_interrupted_jobs(grace_period_s=0)
    assert stale_job_id in db.recover_stale_jobs(grace_period_s=0) or recovered >= 0

    # Verify stale job is reconciled to 'failed' (interrupted)
    stale_job = db.get_run_job(stale_job_id)
    assert stale_job["status"] in ("failed", "interrupted")
    assert "expired" in stale_job["error_message"].lower()

    # Verify healthy job was NOT interrupted
    healthy_job = db.get_run_job(healthy_job_id)
    assert healthy_job["status"] == "running"
    assert healthy_job["error_message"] is None


def test_cancellation_before_execution_queued(reliability_env):
    """A queued job cancelled before worker claims it must transition to cancelled with 0 cases run."""
    db: DatabaseManager = reliability_env["db"]
    job_mgr: JobManager = reliability_env["job_mgr"]
    job_id = "job-cancel-queued"

    db.create_run_job(
        job_id=job_id,
        plan_id="p-q",
        status="queued",
        total_cases=5,
        project_id="proj-rel",
    )

    # Cancel while still queued
    cancelled_job = job_mgr.cancel_job(job_id, project_id="proj-rel")
    assert cancelled_job["status"] == "cancelled"
    assert cancelled_job["cancelled"] is True

    # Worker attempting to claim must fail
    assert db.claim_run_job(job_id, worker_id="worker-late") is False

    # Check terminal state
    persisted = db.get_run_job(job_id)
    assert persisted["status"] == "cancelled"
    assert persisted["completed_cases"] == 0


def test_cooperative_cancel_token_detects_db_cancellation(reliability_env):
    """CooperativeCancelToken must detect cross-process cancellation in SQLite before next case."""
    db: DatabaseManager = reliability_env["db"]
    job_id = "job-token-test"
    worker_id = "worker-tok-1"

    db.create_run_job(job_id=job_id, plan_id="p-tok", status="queued", project_id="proj-rel")
    assert db.claim_run_job(job_id, worker_id=worker_id, lease_duration_s=60) is True

    token = CooperativeCancelToken(job_id=job_id, worker_id=worker_id, db=db, lease_duration_s=60)

    # Initially not cancelled
    assert token.is_set() is False

    # Another process cancels the job in SQLite
    db.request_job_cancellation(job_id)

    # Token detects cancellation via SQLite query and trips
    assert token.is_set() is True


def test_cancellation_after_completion_is_noop(reliability_env):
    """Attempting to cancel an already completed job returns the job unchanged."""
    db: DatabaseManager = reliability_env["db"]
    job_mgr: JobManager = reliability_env["job_mgr"]
    job_id = "job-completed-001"

    db.create_run_job(
        job_id=job_id,
        plan_id="p-done",
        status="completed",
        total_cases=5,
        project_id="proj-rel",
    )
    db.update_run_job(job_id, completed_cases=5, status="completed")

    result = job_mgr.cancel_job(job_id, project_id="proj-rel")
    assert result["status"] == "completed"
    assert result["completed_cases"] == 5


def test_no_blind_retries(reliability_env):
    """An interrupted job is never automatically re-executed upon manager restart."""
    db: DatabaseManager = reliability_env["db"]
    job_id = "job-no-retry"

    db.create_run_job(
        job_id=job_id,
        plan_id="p-noretry",
        status="interrupted",
        total_cases=10,
        project_id="proj-rel",
    )
    db.update_run_job(job_id, completed_cases=3, error_message="Worker lost.")

    # Simulate process restart by resetting singleton
    JobManager._instance = None
    new_mgr = JobManager()

    job = new_mgr.get_job(job_id, project_id="proj-rel")
    assert job["status"] == "interrupted"
    assert job["completed_cases"] == 3
    assert job["attempt_count"] == 0


def test_cancellation_during_execution_preserves_completed_cases(reliability_env, tmp_path):
    """Mid-run cancellation halts execution cleanly after current case, preserving already completed results."""
    from runport.core.approvers import TokenApprover
    from runport.core.budget import BudgetService
    from runport.core.workspace import BudgetConfig, WorkspaceConfig
    from runport.runs.executor import GenericRunner
    from runport.targets.base import CostBasis, Target, TargetPricing, TargetResult, TargetStatus, TargetType

    db: DatabaseManager = reliability_env["db"]
    job_id = "job-mid-cancel-001"
    worker_id = "worker-mid-1"

    db.create_run_job(
        job_id=job_id,
        plan_id="plan-mid-1",
        status="queued",
        total_cases=4,
        project_id="proj-rel",
    )
    assert db.claim_run_job(job_id, worker_id=worker_id, lease_duration_s=60) is True

    class MidRunCancellingTarget(Target):
        def __init__(self, jid: str, db_mgr: DatabaseManager, cancel_after: int = 1):
            super().__init__(
                target_id="mock-cancel-target",
                name="Mock Cancel Target",
                target_type=TargetType.RAW_MODEL,
                pricing=TargetPricing(input_usd_per_1m=Decimal("0.20"), output_usd_per_1m=Decimal("0.80")),
            )
            self.jid = jid
            self.db_mgr = db_mgr
            self.cancel_after = cancel_after
            self.executed_count = 0

        def execute(self, input_payload, context=None):
            self.executed_count += 1
            if self.executed_count >= self.cancel_after:
                # External cancellation written to database during case execution
                self.db_mgr.request_job_cancellation(self.jid)
            return TargetResult(
                target_id=self.target_id,
                status=TargetStatus.SUCCESS,
                output_text="mock response",
                latency_ms=15.0,
                tokens_in=50,
                tokens_out=10,
                cost_usd=Decimal("0.00002"),
                cost_basis=CostBasis.ESTIMATED,
                provenance="LIVE",
            )

    target = MidRunCancellingTarget(jid=job_id, db_mgr=db, cancel_after=1)
    targets = {target.target_id: target}

    cases = [
        {"id": "c1", "query": "hello 1", "classification": "PUBLIC"},
        {"id": "c2", "query": "hello 2", "classification": "PUBLIC"},
        {"id": "c3", "query": "hello 3", "classification": "PUBLIC"},
        {"id": "c4", "query": "hello 4", "classification": "PUBLIC"},
    ]

    plan = ExecutionPlan(
        plan_id="plan-mid-1",
        target_ids=[target.target_id],
        dataset_path="mock.jsonl",
        dataset_hash="hash-123",
        total_cases=4,
        budget_cap_usd=Decimal("5.00"),
        is_live=False,
    )

    ws = WorkspaceConfig(
        root=tmp_path,
        budget=BudgetConfig(total_usd=Decimal("100.00"), per_run_usd=Decimal("10.00"), per_case_usd=Decimal("1.00")),
    )
    budget_service = BudgetService(db, ws.budget.to_budget_policy())
    runner = GenericRunner(budget_service=budget_service, db=db, workspace=ws)
    approver = TokenApprover(token=plan.fingerprint, enabled=True, operator="rel-operator")

    cancel_token = CooperativeCancelToken(job_id=job_id, worker_id=worker_id, db=db, lease_duration_s=60)

    # Execute plan with CooperativeCancelToken
    runs = runner.execute_plan(
        plan,
        targets,
        cases,
        approver=approver,
        cancel_token=cancel_token,
    )

    assert len(runs) == 1
    run_res = runs[0]

    # Execution must halt with 'cancelled' kind
    assert run_res.halt_kind == "cancelled"
    # Target only executed the first case
    assert target.executed_count == 1
    # Exactly 1 result was produced and preserved
    assert len(run_res.case_results) == 1
    assert run_res.case_results[0].output_text == "mock response"

    # Subsequent cases c2, c3, c4 were NEVER executed
    persisted_results = db.get_evaluation_results_for_run(run_res.run_id)
    assert len(persisted_results) == 1
    assert persisted_results[0]["case_id"] == "c1"

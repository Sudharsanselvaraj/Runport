"""Audit remediation regression tests for P0, P1, and P2 findings.

Verifies:
1. MCP Remote Tenant Authorization & Scope Isolation (Finding 1 - P0).
2. Project-Scoped Budget Status & Reconcile Isolation (Finding 2 - P0).
3. Canonical Project ID Spend & Reservation Booking (Finding 3 - P1).
4. Autonomous Background Worker Heartbeat & Ownership Fencing (Finding 4 - P1).
5. Crash Recovery Plan-Bound Reservation Sweeping (Finding 5 - P1).
6. Multi-Target Job Progress & Caller Attribution (Finding 6 - P2).
"""

from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
import threading
import time
import pytest
from starlette.testclient import TestClient

from runport.api.app import create_app
from runport.api.v1.auth import hash_api_key
from runport.api.v1.jobs import JobManager
from runport.core.config import settings
from runport.runs.planner import ExecutionPlan
from runport.services.execution import ExecutionService
from runport.storage.db import DatabaseManager
from runport.targets.base import Target, TargetResult, TargetStatus, TargetType, TargetPricing, BillingMode, CostBasis


@pytest.fixture
def audit_workspace(tmp_path: Path, monkeypatch):
    """Sets up an isolated database, projects, API keys, and test clients."""
    db_file = tmp_path / "audit_remediation.db"
    monkeypatch.setenv("RUNPORT_DB_PATH", str(db_file))
    monkeypatch.setenv("RUNPORT_API_TOKEN", "master-secret-audit-999")
    monkeypatch.setattr(type(settings), "db_path", property(lambda self: db_file))

    db = DatabaseManager(db_file)
    db.init_db()

    # Create two organizations and projects
    with db.get_connection() as conn:
        conn.execute("INSERT OR IGNORE INTO organizations (org_id, name, created_at) VALUES ('org-a', 'Org Alpha', '2026-01-01')")
        conn.execute("INSERT OR IGNORE INTO organizations (org_id, name, created_at) VALUES ('org-b', 'Org Beta', '2026-01-01')")
        conn.execute(
            "INSERT OR IGNORE INTO projects (project_id, org_id, name, settings_json, created_at) VALUES ('proj-a', 'org-a', 'Project Alpha', '{}', '2026-01-01')"
        )
        conn.execute(
            "INSERT OR IGNORE INTO projects (project_id, org_id, name, settings_json, created_at) VALUES ('proj-b', 'org-b', 'Project Beta', '{}', '2026-01-01')"
        )

    raw_key_a = "rp_live_alpha_audit_token_111"
    raw_key_b = "rp_live_beta_audit_token_222"
    all_scopes = [
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
        key_id="key-alpha",
        name="Alpha Operator",
        key_hash=hash_api_key(raw_key_a),
        scopes=all_scopes,
        project_id="proj-a",
        principal="alpha@example.com",
    )
    db.create_api_key(
        key_id="key-beta",
        name="Beta Operator",
        key_hash=hash_api_key(raw_key_b),
        scopes=all_scopes,
        project_id="proj-b",
        principal="beta@example.com",
    )

    JobManager._instance = None
    JobManager()

    app = create_app()
    # Remote client simulating external network access
    remote_client = TestClient(app, client=("198.51.100.99", 54321), base_url="http://runport.example.com")
    local_client = TestClient(app)

    return {
        "db": db,
        "remote_client": remote_client,
        "local_client": local_client,
        "key_a": raw_key_a,
        "key_b": raw_key_b,
        "master_token": "master-secret-audit-999",
        "tmp_path": tmp_path,
    }


# =============================================================================
# Finding 1: MCP Tenant Scoping & Scope Enforcement
# =============================================================================


def test_mcp_cross_tenant_isolation(audit_workspace):
    """Remote MCP calls using Project A credentials cannot inspect or alter Project B resources."""
    db: DatabaseManager = audit_workspace["db"]
    client: TestClient = audit_workspace["remote_client"]
    key_a = audit_workspace["key_a"]
    key_b = audit_workspace["key_b"]
    master_key = audit_workspace["master_token"]

    # Seed an evaluation run for Project B
    run_b_id = "run-beta-sec-001"
    db.save_evaluation_run(
        {
            "run_id": run_b_id,
            "timestamp": "2026-01-01T00:00:00Z",
            "model_id": "beta-model",
            "dataset_path": "data.jsonl",
            "total_cases": 1,
            "completed_cases": 1,
            "failed_cases": 0,
            "total_cost_usd": "0.10",
            "mean_latency_ms": 20.0,
            "mean_accuracy": 1.0,
            "is_dry_run": 0,
            "project_id": "proj-b",
        }
    )

    # Seed an active job for Project B
    job_b = db.create_run_job(
        job_id="job-beta-sec-001",
        plan_id="plan-beta-sec",
        status="running",
        total_cases=5,
        project_id="proj-b",
    )

    # 1. Project A calls get_run for Project B run -> Must return ToolError / isError: True
    req_get_run = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {
            "name": "get_run",
            "arguments": {"run_id": run_b_id},
        },
    }
    res_a = client.post("/mcp/messages", headers={"Authorization": f"Bearer {key_a}"}, json=req_get_run)
    assert res_a.status_code == 200
    data_a = res_a.json()
    assert data_a["result"]["isError"] is True
    assert "no run" in data_a["result"]["content"][0]["text"].lower()

    # 2. Project A calls cancel_job for Project B job -> Must return ToolError
    req_cancel = {
        "jsonrpc": "2.0",
        "id": 2,
        "method": "tools/call",
        "params": {
            "name": "cancel_job",
            "arguments": {"job_id": "job-beta-sec-001"},
        },
    }
    res_cancel_a = client.post("/mcp/messages", headers={"Authorization": f"Bearer {key_a}"}, json=req_cancel)
    assert res_cancel_a.status_code == 200
    data_cancel = res_cancel_a.json()
    assert data_cancel["result"]["isError"] is True
    assert "not found" in data_cancel["result"]["content"][0]["text"].lower()

    # 3. Project A reads resource runport://runs -> Must NOT contain run_b_id
    req_res_runs = {
        "jsonrpc": "2.0",
        "id": 3,
        "method": "resources/read",
        "params": {"uri": "runport://runs"},
    }
    res_runs_a = client.post("/mcp/messages", headers={"Authorization": f"Bearer {key_a}"}, json=req_res_runs)
    assert res_runs_a.status_code == 200
    runs_text = res_runs_a.json()["result"]["contents"][0]["text"]
    assert run_b_id not in runs_text

    # 4. Master token CAN access run_b_id
    res_master = client.post("/mcp/messages", headers={"Authorization": f"Bearer {master_key}"}, json=req_get_run)
    assert res_master.status_code == 200
    data_master = res_master.json()
    assert data_master["result"].get("isError") is not True
    assert run_b_id in data_master["result"]["content"][0]["text"]


# =============================================================================
# Finding 2: Project-Scoped Budget Ledger & Reconciliation Isolation
# =============================================================================


def test_project_budget_status_and_reconciliation_isolation(audit_workspace):
    """Project A cannot view Project B's unresolved spend or reconcile foreign project transactions."""
    db: DatabaseManager = audit_workspace["db"]
    client: TestClient = audit_workspace["local_client"]
    key_a = audit_workspace["key_a"]
    key_b = audit_workspace["key_b"]
    master_key = audit_workspace["master_token"]

    # Record spend:
    # 1. Project A resolved spend ($0.50)
    db.record_transaction(
        transaction_id="tx-alpha-001",
        model_id="alpha-model",
        provider="openrouter",
        amount_usd=Decimal("0.50"),
        description="Alpha case 1",
        project_id="proj-a",
        is_unresolved=False,
        cost_basis="ACTUAL",
    )
    # 2. Project B unresolved spend
    tx_b_unresolved = "tx-beta-unres-001"
    db.record_transaction(
        transaction_id=tx_b_unresolved,
        model_id="beta-model",
        provider="openrouter",
        amount_usd=Decimal("0.00"),
        description="Beta case unresolved",
        project_id="proj-b",
        is_unresolved=True,
        cost_basis="UNRESOLVED",
    )

    # 1. Project A checks GET /api/v1/budget -> Sees 0 unresolved spend
    res_status_a = client.get("/api/v1/budget", headers={"Authorization": f"Bearer {key_a}"})
    assert res_status_a.status_code == 200
    data_status_a = res_status_a.json()
    assert data_status_a["unresolved_count"] == 0
    assert Decimal(str(data_status_a["spend"]["total_spent_usd"])) == Decimal("0.50")
    assert len(data_status_a["unresolved_transactions"]) == 0

    # 2. Project B checks GET /api/v1/budget -> Sees 1 unresolved spend
    res_status_b = client.get("/api/v1/budget", headers={"Authorization": f"Bearer {key_b}"})
    assert res_status_b.status_code == 200
    data_status_b = res_status_b.json()
    assert data_status_b["unresolved_count"] == 1
    assert data_status_b["unresolved_transactions"][0]["transaction_id"] == tx_b_unresolved

    # 3. Project A tries to reconcile Project B's transaction -> Must fail closed with 404 Not Found
    reconcile_payload = {
        "transaction_id": tx_b_unresolved,
        "reconciled_usd": "1.25",
        "notes": "Alpha operator attempting unauthorized reconcile",
    }
    res_reconcile_a = client.post(
        "/api/v1/budget/reconcile",
        headers={"Authorization": f"Bearer {key_a}"},
        json=reconcile_payload,
    )
    assert res_reconcile_a.status_code == 404

    # Verify transaction is still unresolved
    unresolved = db.get_unresolved(project_id="proj-b")
    assert any(u["transaction_id"] == tx_b_unresolved for u in unresolved)

    # 4. Master token CAN reconcile the transaction
    res_reconcile_m = client.post(
        "/api/v1/budget/reconcile",
        headers={"Authorization": f"Bearer {master_key}"},
        json=reconcile_payload,
    )
    assert res_reconcile_m.status_code == 200
    assert res_reconcile_m.json()["status"] == "reconciled"


# =============================================================================
# Finding 3: Canonical Project Propagation in Spend Accounting & Reservations
# =============================================================================


class MockPricedTarget(Target):
    """Deterministic mock target for spend testing."""

    def __init__(self, target_id: str):
        super().__init__(
            target_id=target_id,
            name=target_id,
            target_type=TargetType.RAW_MODEL,
            pricing=TargetPricing(input_usd_per_1m=Decimal("10.00"), output_usd_per_1m=Decimal("30.00")),
            billing=BillingMode.BILLABLE,
        )
        self.provider_name = "test-provider"

    def execute(self, case):
        return TargetResult(
            target_id=self.target_id,
            status=TargetStatus.SUCCESS,
            output_text="Valid test output",
            latency_ms=15.0,
            cost_usd=Decimal("0.045000"),
            cost_basis=CostBasis.ESTIMATED,
            tokens_in=100,
            tokens_out=50,
            request_sent=True,
        )


def test_canonical_project_id_spend_accounting(audit_workspace):
    """ExecutionService.execute() propagates canonical plan.project_id to reservations and ledger."""
    db: DatabaseManager = audit_workspace["db"]
    svc = ExecutionService()

    targets = {"mock-target": MockPricedTarget("mock-target")}
    specs = {"mock-target": {"id": "mock-target"}}
    cases = [{"id": "case-01", "input": "Hello world", "classification": "PUBLIC"}]

    summary = svc.plan(
        targets=targets,
        specs=specs,
        cases=cases,
        dataset_label="eval_cases",
        requested_by="alpha@example.com",
        project_id="proj-a",
    )

    svc.approve(
        plan_id=summary.plan_id,
        fingerprint=summary.fingerprint,
        channel="cli_interactive",
        approver="test-approver",
        project_id="proj-a",
    )

    outcome = svc.execute(
        plan_id=summary.plan_id,
        targets=targets,
        specs=specs,
        cases=cases,
    )

    assert len(outcome.runs) == 1
    run_res = outcome.runs[0]
    assert run_res.successful_cases == 1

    # Verify run persisted with proj-a
    run_row = db.get_evaluation_run(run_res.run_id)
    assert run_row is not None
    assert run_row["project_id"] == "proj-a"

    # Verify budget_ledger entry has project_id == "proj-a" (NOT "default")
    with db.get_connection() as conn:
        tx_row = conn.execute(
            "SELECT project_id, amount_micros, cost_basis FROM budget_ledger WHERE run_id = ?",
            (run_res.run_id,),
        ).fetchone()
        assert tx_row is not None
        assert tx_row["project_id"] == "proj-a"
        assert tx_row["cost_basis"] == "ESTIMATED"


# =============================================================================
# Finding 4: Autonomous Background Worker Heartbeat & Ownership Fencing
# =============================================================================


class SlowSimulatedTarget(Target):
    """Target simulating a long network call to verify periodic heartbeat renewal."""

    def __init__(self, target_id: str, sleep_s: float = 1.0):
        super().__init__(
            target_id=target_id,
            name=target_id,
            target_type=TargetType.RAW_MODEL,
            billing=BillingMode.LOCAL,
        )
        self.sleep_s = sleep_s

    def execute(self, case):
        time.sleep(self.sleep_s)
        return TargetResult(
            target_id=self.target_id,
            status=TargetStatus.SUCCESS,
            output_text="Slow target finished",
            latency_ms=self.sleep_s * 1000,
            cost_usd=Decimal("0.00"),
            cost_basis="UNAVAILABLE",
        )


def test_worker_ownership_fencing_prevents_stale_overwrites(audit_workspace):
    """Worker ownership fencing rejects updates from workers who lost their lease."""
    db: DatabaseManager = audit_workspace["db"]

    job = db.create_run_job(
        job_id="job-fence-001",
        plan_id="plan-fence-001",
        status="running",
        worker_id="worker-original",
        lease_expires_at="2020-01-01T00:00:00Z",
        project_id="proj-a",
    )
    assert job is not None

    # Worker B claims the job after lease expired
    claimed = db.claim_run_job("job-fence-001", worker_id="worker-new", lease_duration_s=60)
    assert claimed is True

    # Worker A attempts to update progress with expected_worker_id="worker-original"
    updated = db.update_run_job(
        "job-fence-001",
        completed_cases=10,
        expected_worker_id="worker-original",
    )
    assert updated is False  # Fencing prevented stale overwrite!

    # Worker B's update succeeds
    updated_b = db.update_run_job(
        "job-fence-001",
        completed_cases=10,
        expected_worker_id="worker-new",
    )
    assert updated_b is True


def test_autonomous_heartbeat_renewal_during_long_call(audit_workspace, monkeypatch):
    """Worker periodically renews heartbeat lease in an independent thread during slow executions."""
    db: DatabaseManager = audit_workspace["db"]
    from runport.api.v1.jobs import JobContext

    job_mgr = JobManager()

    job_id = "job-hb-001"
    run_id = "run-hb-001"

    svc = ExecutionService()
    slow_target = SlowSimulatedTarget("slow-target", sleep_s=0.35)
    targets = {"slow-target": slow_target}
    specs = {"slow-target": {"id": "slow-target", "type": "raw_model"}}

    # Ensure ExecutionService resolves our slow target
    monkeypatch.setattr(ExecutionService, "resolve", lambda self, tids, **kw: (targets, specs))

    dataset_file = audit_workspace["tmp_path"] / "hb_cases.jsonl"
    dataset_file.write_text('{"id": "c1", "input": "test", "classification": "PUBLIC"}\n')
    cases = [{"id": "c1", "input": "test", "classification": "PUBLIC"}]

    summary = svc.plan(
        targets=targets,
        specs=specs,
        cases=cases,
        dataset_label="eval_cases",
        requested_by="alpha@example.com",
        project_id="proj-a",
    )
    svc.approve(
        plan_id=summary.plan_id,
        fingerprint=summary.fingerprint,
        channel="cli_interactive",
        approver="test-approver",
        project_id="proj-a",
    )

    db.create_run_job(
        job_id=job_id,
        plan_id=summary.plan_id,
        status="queued",
        total_cases=1,
        run_id=run_id,
        project_id="proj-a",
    )

    ctx = JobContext(job_id=job_id, plan_id=summary.plan_id, project_id="proj-a")

    # Execute worker with fast heartbeat interval (0.05s)
    worker_t = threading.Thread(
        target=job_mgr._run_job_worker,
        args=(ctx, run_id, ["slow-target"], str(dataset_file), 1),
        kwargs={"heartbeat_interval_s": 0.05},
    )
    worker_t.start()

    # Wait briefly while target is sleeping (0.35s) to inspect heartbeat in database
    time.sleep(0.2)
    job_mid = db.get_run_job(job_id, project_id="proj-a")
    assert job_mid is not None
    assert job_mid["status"] == "running"
    first_hb = job_mid.get("heartbeat_at")
    assert first_hb is not None

    worker_t.join(timeout=5.0)
    job_done = db.get_run_job(job_id, project_id="proj-a")
    assert job_done is not None
    assert job_done["status"] == "completed"


# =============================================================================
# Finding 5: Crash Recovery Sweep of Plan-Bound Reservations
# =============================================================================


def test_crash_recovery_sweeps_plan_bound_reservations(audit_workspace):
    """Stale job crash recovery releases reservations bound to plan_id even with mismatched run_ids."""
    db: DatabaseManager = audit_workspace["db"]

    job_id = "job-crash-999"
    plan_id = "plan-crash-999"
    job_run_id = "run-job-record-001"
    runner_run_id = "run-runner-internal-999"  # Different run_id created by executor

    # 1. Create a stale running job whose lease expired in the past
    past_expiry = "2026-01-01T00:00:00Z"
    db.create_run_job(
        job_id=job_id,
        plan_id=plan_id,
        status="running",
        run_id=job_run_id,
        worker_id="worker-crashed",
        lease_expires_at=past_expiry,
        project_id="proj-a",
    )

    # 2. Insert an open reservation bound to runner_run_id AND plan_id
    res_refused = db.reserve_budget(
        reservation_id="rsv-crash-001",
        run_id=runner_run_id,
        amount_usd=Decimal("2.50"),
        total_cap_usd=Decimal("100.00"),
        run_cap_usd=Decimal("50.00"),
        pilot_cap_usd=Decimal("50.00"),
        is_pilot=True,
        ttl_s=3600,
        project_id="proj-a",
        plan_id=plan_id,
    )
    assert res_refused is None  # Reservation accepted

    # Verify reservation exists
    with db.get_connection() as conn:
        count = conn.execute("SELECT COUNT(*) FROM budget_reservations WHERE plan_id = ?", (plan_id,)).fetchone()[0]
        assert count == 1

    # 3. Trigger crash recovery
    recovered = db.recover_stale_jobs(grace_period_s=0)
    assert job_id in recovered

    # 4. Verify reservation was cleanly deleted by plan_id
    with db.get_connection() as conn:
        count_after = conn.execute("SELECT COUNT(*) FROM budget_reservations WHERE plan_id = ?", (plan_id,)).fetchone()[0]
        assert count_after == 0


# =============================================================================
# Finding 6: Multi-Target Progress Calculation & Caller Attribution
# =============================================================================


def test_multi_target_job_progress_and_requested_by(audit_workspace):
    """JobManager.submit_job() calculates total_cases across all targets and persists requested_by."""
    db: DatabaseManager = audit_workspace["db"]
    job_mgr = JobManager()
    tmp_path = audit_workspace["tmp_path"]

    # Write a test dataset with 4 cases
    dataset_file = tmp_path / "multi_target_data.jsonl"
    dataset_file.write_text(
        '{"id": "1", "input": "c1", "classification": "PUBLIC"}\n'
        '{"id": "2", "input": "c2", "classification": "PUBLIC"}\n'
        '{"id": "3", "input": "c3", "classification": "PUBLIC"}\n'
        '{"id": "4", "input": "c4", "classification": "PUBLIC"}\n'
    )

    # Submit job with 3 targets -> Total cases must be 4 * 3 = 12
    job = job_mgr.submit_job(
        plan_id="plan-multi-001",
        target_ids=["target-1", "target-2", "target-3"],
        dataset_path=str(dataset_file),
        requested_by="admin-user@example.com",
        project_id="proj-a",
        requested_by_key_id="key-alpha",
    )

    assert job["total_cases"] == 12
    assert job["requested_by"] == "admin-user@example.com"
    assert job["project_id"] == "proj-a"

    # Verify database record also preserved requested_by
    persisted = db.get_run_job(job["job_id"], project_id="proj-a")
    assert persisted is not None
    assert persisted["total_cases"] == 12
    assert persisted.get("requested_by") == "admin-user@example.com"
    job_mgr.cancel_job(job["job_id"], project_id="proj-a")


# =============================================================================
# Additional Findings: Least-Privilege MCP Scopes, Cross-Project Plan Execution,
# and Fail-Closed Heartbeat Outage
# =============================================================================


def test_mcp_least_privilege_scope_enforcement(audit_workspace):
    """MCP enforces granted API key scopes on tools and returns ToolError with isError: True when scope is missing."""
    db: DatabaseManager = audit_workspace["db"]
    client: TestClient = audit_workspace["remote_client"]

    # 1. Create an API key with ONLY 'runs:read' scope
    key_readonly = "rp_live_alpha_readonly_token_888"
    db.create_api_key(
        key_id="key-alpha-readonly",
        name="Alpha Read-Only",
        key_hash=hash_api_key(key_readonly),
        scopes=["runs:read"],
        project_id="proj-a",
        principal="readonly@example.com",
    )

    auth_header = {"Authorization": f"Bearer {key_readonly}"}

    # runs:read is permitted for get_run
    res_run = client.post(
        "/mcp/messages",
        headers=auth_header,
        json={"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": "get_run", "arguments": {"run_id": "nonexistent"}}},
    )
    assert res_run.status_code == 200
    # Fails because run doesn't exist, NOT because of scope
    assert "Forbidden: credential lacks required scope" not in res_run.json()["result"]["content"][0]["text"]

    # Forbidden: create_benchmark_plan requires plans:create
    res_plan = client.post(
        "/mcp/messages",
        headers=auth_header,
        json={
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {"name": "create_benchmark_plan", "arguments": {"target_ids": ["dummy"], "dataset_name": "eval.jsonl"}},
        },
    )
    assert res_plan.status_code == 200
    plan_data = res_plan.json()
    assert plan_data["result"]["isError"] is True
    assert "Forbidden: credential lacks required scope 'plans:create'" in plan_data["result"]["content"][0]["text"]

    # Forbidden: execute_approved_benchmark requires runs:execute
    res_exec = client.post(
        "/mcp/messages",
        headers=auth_header,
        json={"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": "execute_approved_benchmark", "arguments": {"plan_id": "plan-123"}}},
    )
    assert res_exec.status_code == 200
    exec_data = res_exec.json()
    assert exec_data["result"]["isError"] is True
    assert "Forbidden: credential lacks required scope 'runs:execute'" in exec_data["result"]["content"][0]["text"]

    # Forbidden: cancel_job requires runs:execute
    res_cancel = client.post(
        "/mcp/messages",
        headers=auth_header,
        json={"jsonrpc": "2.0", "id": 4, "method": "tools/call", "params": {"name": "cancel_job", "arguments": {"job_id": "job-123"}}},
    )
    assert res_cancel.status_code == 200
    cancel_data = res_cancel.json()
    assert cancel_data["result"]["isError"] is True
    assert "Forbidden: credential lacks required scope 'runs:execute'" in cancel_data["result"]["content"][0]["text"]

    # Forbidden: get_budget_status requires budget:read
    res_budget = client.post(
        "/mcp/messages",
        headers=auth_header,
        json={"jsonrpc": "2.0", "id": 5, "method": "tools/call", "params": {"name": "get_budget_status", "arguments": {}}},
    )
    assert res_budget.status_code == 200
    budget_data = res_budget.json()
    assert budget_data["result"]["isError"] is True
    assert "Forbidden: credential lacks required scope 'budget:read'" in budget_data["result"]["content"][0]["text"]


def test_mcp_resource_scope_enforcement(audit_workspace):
    """MCP enforces required scopes when reading resources."""
    db: DatabaseManager = audit_workspace["db"]
    client: TestClient = audit_workspace["remote_client"]

    # Create an API key with ONLY 'runs:read' scope
    key_readonly = "rp_live_alpha_readonly_token_777"
    db.create_api_key(
        key_id="key-alpha-res-readonly",
        name="Alpha Resource Read-Only",
        key_hash=hash_api_key(key_readonly),
        scopes=["runs:read"],
        project_id="proj-a",
        principal="res_readonly@example.com",
    )
    auth_header = {"Authorization": f"Bearer {key_readonly}"}

    # Reading runport://runs is allowed for runs:read
    res_runs = client.post(
        "/mcp/messages",
        headers=auth_header,
        json={"jsonrpc": "2.0", "id": 1, "method": "resources/read", "params": {"uri": "runport://runs"}},
    )
    assert res_runs.status_code == 200
    assert "error" not in res_runs.json()
    assert res_runs.json()["result"]["contents"][0]["uri"] == "runport://runs"

    # Reading runport://budget requires budget:read -> Must fail with InvalidParams (-32602)
    res_budget = client.post(
        "/mcp/messages",
        headers=auth_header,
        json={"jsonrpc": "2.0", "id": 2, "method": "resources/read", "params": {"uri": "runport://budget"}},
    )
    assert res_budget.status_code == 200
    budget_res = res_budget.json()
    assert "error" in budget_res
    assert budget_res["error"]["code"] == -32602
    assert "Forbidden: credential lacks required scope 'budget:read'" in budget_res["error"]["message"]


def test_mcp_cross_project_approved_plan_execution_prevented(audit_workspace, monkeypatch):
    """Remote MCP execution tool rejects attempts by Project A to execute Project B's approved plan."""
    client: TestClient = audit_workspace["remote_client"]
    key_a = audit_workspace["key_a"]
    svc = ExecutionService()

    sim_target = SlowSimulatedTarget("plan-sec-target", sleep_s=0.01)
    targets = {"plan-sec-target": sim_target}
    specs = {"plan-sec-target": {"id": "plan-sec-target", "type": "raw_model"}}
    monkeypatch.setattr(ExecutionService, "resolve", lambda self, tids, **kw: (targets, specs))

    cases = [{"id": "c1", "input": "test", "classification": "PUBLIC"}]
    # Plan created and approved under Project B
    summary_b = svc.plan(
        targets=targets,
        specs=specs,
        cases=cases,
        dataset_label="eval_cases",
        requested_by="beta@example.com",
        project_id="proj-b",
    )
    svc.approve(
        plan_id=summary_b.plan_id,
        fingerprint=summary_b.fingerprint,
        channel="cli_interactive",
        approver="beta-approver",
        project_id="proj-b",
    )

    # Project A client (with full scopes) attempts to execute Project B's plan
    req_exec = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {
            "name": "execute_approved_benchmark",
            "arguments": {"plan_id": summary_b.plan_id},
        },
    }
    res = client.post("/mcp/messages", headers={"Authorization": f"Bearer {key_a}"}, json=req_exec)
    assert res.status_code == 200
    data = res.json()
    assert data["result"]["isError"] is True
    err_text = data["result"]["content"][0]["text"].lower()
    assert "no plan" in err_text or "not found" in err_text or "refused" in err_text or "not executed" in err_text


def test_execution_service_independent_project_validation(audit_workspace, monkeypatch):
    """ExecutionService independently rejects execution if plan belongs to a different project."""
    from runport.services.approvals import ApprovalError

    svc = ExecutionService()
    sim_target = SlowSimulatedTarget("plan-sec-target-2", sleep_s=0.01)
    targets = {"plan-sec-target-2": sim_target}
    specs = {"plan-sec-target-2": {"id": "plan-sec-target-2", "type": "raw_model"}}
    monkeypatch.setattr(ExecutionService, "resolve", lambda self, tids, **kw: (targets, specs))

    cases = [{"id": "c1", "input": "test", "classification": "PUBLIC"}]
    summary_b = svc.plan(
        targets=targets,
        specs=specs,
        cases=cases,
        dataset_label="eval_cases",
        requested_by="beta@example.com",
        project_id="proj-b",
    )
    svc.approve(
        plan_id=summary_b.plan_id,
        fingerprint=summary_b.fingerprint,
        channel="cli_interactive",
        approver="beta-approver",
        project_id="proj-b",
    )

    # 1. execute_by_ids with foreign project_id
    with pytest.raises(ApprovalError) as exc_info1:
        svc.execute_by_ids(summary_b.plan_id, cases, project_id="proj-a")
    assert "no plan" in str(exc_info1.value).lower() or "belongs to another project" in str(exc_info1.value).lower()

    # 2. execute with foreign project_id
    with pytest.raises(ApprovalError) as exc_info2:
        svc.execute(summary_b.plan_id, targets, specs, cases, project_id="proj-a")
    assert "no plan" in str(exc_info2.value).lower() or "belongs to another project" in str(exc_info2.value).lower()


def test_heartbeat_consecutive_db_failures_fail_closed(audit_workspace, monkeypatch):
    """Worker immediately aborts execution when consecutive heartbeat lease renewals fail 3 times."""
    import sqlite3
    from runport.api.v1.jobs import JobContext

    db: DatabaseManager = audit_workspace["db"]
    job_mgr = JobManager()

    job_id = "job-hb-fail-001"
    run_id = "run-hb-fail-001"

    svc = ExecutionService()
    slow_target = SlowSimulatedTarget("slow-target-fail", sleep_s=0.15)
    targets = {"slow-target-fail": slow_target}
    specs = {"slow-target-fail": {"id": "slow-target-fail", "type": "raw_model"}}
    monkeypatch.setattr(ExecutionService, "resolve", lambda self, tids, **kw: (targets, specs))

    dataset_file = audit_workspace["tmp_path"] / "hb_fail_cases.jsonl"
    dataset_file.write_text(
        '{"id": "c1", "input": "test1", "classification": "PUBLIC"}\n'
        '{"id": "c2", "input": "test2", "classification": "PUBLIC"}\n'
        '{"id": "c3", "input": "test3", "classification": "PUBLIC"}\n'
    )
    cases = [
        {"id": "c1", "input": "test1", "classification": "PUBLIC"},
        {"id": "c2", "input": "test2", "classification": "PUBLIC"},
        {"id": "c3", "input": "test3", "classification": "PUBLIC"},
    ]

    summary = svc.plan(
        targets=targets,
        specs=specs,
        cases=cases,
        dataset_label="eval_cases",
        requested_by="alpha@example.com",
        project_id="proj-a",
    )
    svc.approve(
        plan_id=summary.plan_id,
        fingerprint=summary.fingerprint,
        channel="cli_interactive",
        approver="test-approver",
        project_id="proj-a",
    )

    db.create_run_job(
        job_id=job_id,
        plan_id=summary.plan_id,
        status="queued",
        total_cases=3,
        run_id=run_id,
        project_id="proj-a",
    )

    # Monkeypatch renew_job_lease on DatabaseManager to simulate repeated database connection failures
    fail_attempts = 0

    def failing_renew(self, jid, wid, lease_duration_s=60):
        nonlocal fail_attempts
        fail_attempts += 1
        raise sqlite3.OperationalError("database is locked (simulated failure)")

    monkeypatch.setattr(DatabaseManager, "renew_job_lease", failing_renew)

    ctx = JobContext(job_id=job_id, plan_id=summary.plan_id, project_id="proj-a")

    # Run with very fast heartbeat interval: 0.03s -> 3 failures occur within ~0.10s
    worker_t = threading.Thread(
        target=job_mgr._run_job_worker,
        args=(ctx, run_id, ["slow-target-fail"], str(dataset_file), 3),
        kwargs={"heartbeat_interval_s": 0.03},
    )
    worker_t.start()
    worker_t.join(timeout=3.0)
    assert not worker_t.is_alive()

    # Verify that consecutive failures occurred and reached threshold 3
    assert fail_attempts >= 3

    # Verify that the job was interrupted fail-closed
    job_record = db.get_run_job(job_id, project_id="proj-a")
    assert job_record is not None
    assert job_record["status"] == "interrupted"
    assert job_record["completed_cases"] < 3

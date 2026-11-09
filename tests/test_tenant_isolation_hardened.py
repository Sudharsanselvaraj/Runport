"""Hardened tenant isolation regression tests.

Verifies the primary release gate invariant:
API Key A must NEVER be able to retrieve, export, approve, execute, inspect,
or cancel Project B's resources unless an explicitly authorized master policy
permits it. Cross-project unauthorized access strictly returns 404 Not Found
to prevent resource ID enumeration.
"""

from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
import pytest
from starlette.testclient import TestClient

from runport.api.app import create_app
from runport.api.v1.auth import hash_api_key
from runport.core.config import settings
from runport.runs.planner import ExecutionPlan
from runport.services.approvals import ApprovalStore
from runport.services.execution import ExecutionService
from runport.storage.db import DatabaseManager
from runport.traces.domain import SpanKind, SpanStatus, Trace, Span
from runport.traces.repository import TraceRepository


@pytest.fixture
def isolated_workspace(tmp_path: Path, monkeypatch):
    """Sets up an isolated database, config, and test client."""
    db_file = tmp_path / "tenant_isolation.db"
    monkeypatch.setenv("RUNPORT_DB_PATH", str(db_file))
    monkeypatch.setenv("RUNPORT_API_TOKEN", "master-secret-key-999")
    monkeypatch.setattr(type(settings), "db_path", property(lambda self: db_file))

    db = DatabaseManager(db_file)
    db.init_db()

    # Create two distinct organizations & projects
    with db.get_connection() as conn:
        conn.execute("INSERT OR IGNORE INTO organizations (org_id, name, created_at) VALUES ('org-a', 'Org Alpha', '2026-01-01')")
        conn.execute("INSERT OR IGNORE INTO organizations (org_id, name, created_at) VALUES ('org-b', 'Org Beta', '2026-01-01')")
        conn.execute(
            "INSERT OR IGNORE INTO projects (project_id, org_id, name, settings_json, created_at) VALUES ('proj-a', 'org-a', 'Project Alpha', '{}', '2026-01-01')"
        )
        conn.execute(
            "INSERT OR IGNORE INTO projects (project_id, org_id, name, settings_json, created_at) VALUES ('proj-b', 'org-b', 'Project Beta', '{}', '2026-01-01')"
        )

    # Create API keys for proj-a and proj-b with full scopes
    raw_key_a = "rp_live_alpha_1234567890abcdef"
    raw_key_b = "rp_live_beta_1234567890abcdef"
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
        key_id="key-alpha",
        name="Alpha Operator",
        key_hash=hash_api_key(raw_key_a),
        scopes=full_scopes,
        project_id="proj-a",
        principal="operator-a@alpha.local",
    )

    db.create_api_key(
        key_id="key-beta",
        name="Beta Operator",
        key_hash=hash_api_key(raw_key_b),
        scopes=full_scopes,
        project_id="proj-b",
        principal="operator-b@beta.local",
    )

    # Reset JobManager singleton for isolated test environment
    from runport.api.v1.jobs import JobManager

    JobManager._instance = None
    JobManager()

    app = create_app()
    client = TestClient(app)

    return {
        "db": db,
        "client": client,
        "raw_key_a": raw_key_a,
        "raw_key_b": raw_key_b,
        "master_token": "master-secret-key-999",
    }


def test_anti_enumeration_on_evaluation_runs_and_results(isolated_workspace):
    """API Key A must receive 404 Not Found when attempting to access Project B's runs and results."""
    db: DatabaseManager = isolated_workspace["db"]
    client: TestClient = isolated_workspace["client"]
    key_a = isolated_workspace["raw_key_a"]
    key_b = isolated_workspace["raw_key_b"]
    master_key = isolated_workspace["master_token"]

    # Seed an evaluation run belonging to proj-b
    run_b_id = "run-beta-001"
    db.save_evaluation_run(
        {
            "run_id": run_b_id,
            "timestamp": "2026-01-01T00:00:00Z",
            "model_id": "test-model",
            "dataset_path": "data.jsonl",
            "total_cases": 1,
            "completed_cases": 1,
            "failed_cases": 0,
            "total_cost_usd": "0.05",
            "mean_latency_ms": 100.0,
            "mean_accuracy": 1.0,
            "mean_groundedness": 1.0,
            "mean_overall_score": 1.0,
            "is_dry_run": False,
            "notes": "beta run",
            "project_id": "proj-b",
        }
    )
    db.save_evaluation_results(
        [
            {
                "result_id": "res-beta-001",
                "run_id": run_b_id,
                "case_id": "case-1",
                "prompt": "hello",
                "expected_answer": "hi",
                "generated_output": "hi",
            }
        ]
    )

    # 1. Project B operator can access run and results
    resp_b_run = client.get(f"/api/v1/runs/{run_b_id}", headers={"Authorization": f"Bearer {key_b}"})
    assert resp_b_run.status_code == 200
    assert resp_b_run.json()["run_id"] == run_b_id
    assert resp_b_run.json()["project_id"] == "proj-b"

    resp_b_res = client.get(f"/api/v1/runs/{run_b_id}/results", headers={"Authorization": f"Bearer {key_b}"})
    assert resp_b_res.status_code == 200
    assert len(resp_b_res.json()["results"]) == 1

    # 2. Project A operator MUST receive 404 Not Found (anti-enumeration)
    resp_a_run = client.get(f"/api/v1/runs/{run_b_id}", headers={"Authorization": f"Bearer {key_a}"})
    assert resp_a_run.status_code == 404
    assert "not found" in resp_a_run.text.lower()

    resp_a_res = client.get(f"/api/v1/runs/{run_b_id}/results", headers={"Authorization": f"Bearer {key_a}"})
    assert resp_a_res.status_code == 404
    assert "not found" in resp_a_res.text.lower()

    # 3. Master token retains cross-project platform visibility
    resp_master_run = client.get(f"/api/v1/runs/{run_b_id}", headers={"Authorization": f"Bearer {master_key}"})
    assert resp_master_run.status_code == 200
    assert resp_master_run.json()["run_id"] == run_b_id


def test_anti_enumeration_on_traces_and_exports(isolated_workspace):
    """API Key A must receive 404 Not Found when accessing or exporting Project B's traces."""
    db: DatabaseManager = isolated_workspace["db"]
    client: TestClient = isolated_workspace["client"]
    key_a = isolated_workspace["raw_key_a"]
    key_b = isolated_workspace["raw_key_b"]
    master_key = isolated_workspace["master_token"]

    repo = TraceRepository(db=db)
    trace_b = Trace(
        trace_id="tr-beta-999",
        name="beta_agent_trace",
        status=SpanStatus.OK,
        project_id="proj-b",
        created_at=datetime.now(timezone.utc),
        spans=[
            Span(
                trace_id="tr-beta-999",
                span_id="sp-beta-1",
                name="llm_call",
                kind=SpanKind.LLM,
                status=SpanStatus.OK,
            )
        ],
    )
    repo.save_trace(trace_b, project_id="proj-b")

    # 1. Project B operator can retrieve and export
    resp_b = client.get(f"/api/v1/traces/{trace_b.trace_id}", headers={"Authorization": f"Bearer {key_b}"})
    assert resp_b.status_code == 200
    assert resp_b.json()["trace_id"] == trace_b.trace_id

    resp_b_otlp = client.get(f"/api/v1/traces/{trace_b.trace_id}/otlp", headers={"Authorization": f"Bearer {key_b}"})
    assert resp_b_otlp.status_code == 200

    resp_b_langfuse = client.get(f"/api/v1/traces/{trace_b.trace_id}/langfuse", headers={"Authorization": f"Bearer {key_b}"})
    assert resp_b_langfuse.status_code == 200

    # 2. Project A operator MUST receive 404 Not Found
    resp_a = client.get(f"/api/v1/traces/{trace_b.trace_id}", headers={"Authorization": f"Bearer {key_a}"})
    assert resp_a.status_code == 404

    resp_a_otlp = client.get(f"/api/v1/traces/{trace_b.trace_id}/otlp", headers={"Authorization": f"Bearer {key_a}"})
    assert resp_a_otlp.status_code == 404

    resp_a_langfuse = client.get(f"/api/v1/traces/{trace_b.trace_id}/langfuse", headers={"Authorization": f"Bearer {key_a}"})
    assert resp_a_langfuse.status_code == 404

    # 3. Master token retains visibility
    resp_master = client.get(f"/api/v1/traces/{trace_b.trace_id}", headers={"Authorization": f"Bearer {master_key}"})
    assert resp_master.status_code == 200


def test_anti_enumeration_on_plans_and_approvals(isolated_workspace):
    """API Key A must receive 404 Not Found when retrieving or approving Project B's plans."""
    db: DatabaseManager = isolated_workspace["db"]
    client: TestClient = isolated_workspace["client"]
    key_a = isolated_workspace["raw_key_a"]
    key_b = isolated_workspace["raw_key_b"]

    store = ApprovalStore(db=db)
    rec_b = store.register(
        fingerprint="fp-beta-12345",
        summary={
            "target_ids": ["mock-model"],
            "case_count": 2,
            "dataset_label": "data.jsonl",
            "projected_max_cost_usd": "5.00",
            "per_target": [],
            "blockers": [],
        },
        requested_by="operator-b@beta.local",
        project_id="proj-b",
    )

    # 1. Project B operator can view plan
    resp_b = client.get(f"/api/v1/plans/{rec_b.plan_id}", headers={"Authorization": f"Bearer {key_b}"})
    assert resp_b.status_code == 200
    assert resp_b.json()["plan_id"] == rec_b.plan_id

    # 2. Project A operator receives 404 on GET and POST /approve
    resp_a_get = client.get(f"/api/v1/plans/{rec_b.plan_id}", headers={"Authorization": f"Bearer {key_a}"})
    assert resp_a_get.status_code == 404

    resp_a_approve = client.post(
        f"/api/v1/plans/{rec_b.plan_id}/approve",
        headers={"Authorization": f"Bearer {key_a}"},
        json={"fingerprint": rec_b.fingerprint, "approver": "Malicious Actor"},
    )
    assert resp_a_approve.status_code == 404

    # 3. Project A operator cannot launch a run for Project B's plan
    resp_a_run = client.post(
        f"/api/v1/plans/{rec_b.plan_id}/runs",
        headers={"Authorization": f"Bearer {key_a}"},
    )
    assert resp_a_run.status_code == 404


def test_anti_enumeration_on_jobs_and_cancellation(isolated_workspace):
    """API Key A must receive 404 Not Found when inspecting or cancelling Project B's background jobs."""
    db: DatabaseManager = isolated_workspace["db"]
    client: TestClient = isolated_workspace["client"]
    key_a = isolated_workspace["raw_key_a"]
    key_b = isolated_workspace["raw_key_b"]

    job_b_id = "job-beta-777"
    db.create_run_job(
        job_id=job_b_id,
        plan_id="plan-b",
        status="RUNNING",
        total_cases=10,
        project_id="proj-b",
        requested_by_key_id="beta-key-id",
    )

    # 1. Project B operator can view job
    resp_b = client.get(f"/api/v1/jobs/{job_b_id}", headers={"Authorization": f"Bearer {key_b}"})
    assert resp_b.status_code == 200
    assert resp_b.json()["job_id"] == job_b_id

    # 2. Project A operator receives 404 on GET and POST /cancel
    resp_a_get = client.get(f"/api/v1/jobs/{job_b_id}", headers={"Authorization": f"Bearer {key_a}"})
    assert resp_a_get.status_code == 404

    resp_a_cancel = client.post(f"/api/v1/jobs/{job_b_id}/cancel", headers={"Authorization": f"Bearer {key_a}"})
    assert resp_a_cancel.status_code == 404

    # Verify job was NOT cancelled by Project A attempt
    assert db.get_run_job(job_b_id)["cancelled"] == 0

    # 3. Project B operator cancels cleanly
    resp_b_cancel = client.post(f"/api/v1/jobs/{job_b_id}/cancel", headers={"Authorization": f"Bearer {key_b}"})
    assert resp_b_cancel.status_code == 200
    assert bool(db.get_run_job(job_b_id)["cancelled"]) is True


def test_collection_endpoints_strict_project_filtering(isolated_workspace):
    """Collection endpoints (runs, traces, jobs) must return ONLY resources owned by the caller's project."""
    db: DatabaseManager = isolated_workspace["db"]
    client: TestClient = isolated_workspace["client"]
    key_a = isolated_workspace["raw_key_a"]
    key_b = isolated_workspace["raw_key_b"]
    master_key = isolated_workspace["master_token"]

    # Seed resources in both projects
    db.save_evaluation_run(
        {
            "run_id": "run-alpha-1",
            "timestamp": "2026-01-01T00:00:00Z",
            "model_id": "m1",
            "dataset_path": "d1.jsonl",
            "total_cases": 1,
            "completed_cases": 1,
            "failed_cases": 0,
            "total_cost_usd": "0.01",
            "mean_latency_ms": 100.0,
            "mean_accuracy": 1.0,
            "mean_groundedness": 1.0,
            "mean_overall_score": 1.0,
            "is_dry_run": False,
            "notes": "alpha run",
            "project_id": "proj-a",
        }
    )
    db.save_evaluation_run(
        {
            "run_id": "run-beta-1",
            "timestamp": "2026-01-01T00:00:00Z",
            "model_id": "m2",
            "dataset_path": "d2.jsonl",
            "total_cases": 1,
            "completed_cases": 1,
            "failed_cases": 0,
            "total_cost_usd": "0.02",
            "mean_latency_ms": 100.0,
            "mean_accuracy": 1.0,
            "mean_groundedness": 1.0,
            "mean_overall_score": 1.0,
            "is_dry_run": False,
            "notes": "beta run",
            "project_id": "proj-b",
        }
    )

    db.create_run_job(job_id="job-alpha-1", plan_id="p-a", status="RUNNING", project_id="proj-a")
    db.create_run_job(job_id="job-beta-1", plan_id="p-b", status="RUNNING", project_id="proj-b")

    repo = TraceRepository(db=db)
    repo.save_trace(Trace(trace_id="tr-alpha-1", name="t-a", project_id="proj-a"), project_id="proj-a")
    repo.save_trace(Trace(trace_id="tr-beta-1", name="t-b", project_id="proj-b"), project_id="proj-b")

    # Key A only sees Alpha resources
    runs_a = client.get("/api/v1/runs", headers={"Authorization": f"Bearer {key_a}"}).json()
    assert [r["run_id"] for r in runs_a] == ["run-alpha-1"]

    jobs_a = client.get("/api/v1/jobs", headers={"Authorization": f"Bearer {key_a}"}).json()
    assert [j["job_id"] for j in jobs_a] == ["job-alpha-1"]

    traces_a = client.get("/api/v1/traces", headers={"Authorization": f"Bearer {key_a}"}).json()
    assert [t["trace_id"] for t in traces_a] == ["tr-alpha-1"]

    # Key B only sees Beta resources
    runs_b = client.get("/api/v1/runs", headers={"Authorization": f"Bearer {key_b}"}).json()
    assert [r["run_id"] for r in runs_b] == ["run-beta-1"]

    jobs_b = client.get("/api/v1/jobs", headers={"Authorization": f"Bearer {key_b}"}).json()
    assert [j["job_id"] for j in jobs_b] == ["job-beta-1"]

    traces_b = client.get("/api/v1/traces", headers={"Authorization": f"Bearer {key_b}"}).json()
    assert [t["trace_id"] for t in traces_b] == ["tr-beta-1"]

    # Master token sees all resources across all projects
    runs_m = client.get("/api/v1/runs", headers={"Authorization": f"Bearer {master_key}"}).json()
    assert set(r["run_id"] for r in runs_m) >= {"run-alpha-1", "run-beta-1"}

    jobs_m = client.get("/api/v1/jobs", headers={"Authorization": f"Bearer {master_key}"}).json()
    assert set(j["job_id"] for j in jobs_m) >= {"job-alpha-1", "job-beta-1"}

    traces_m = client.get("/api/v1/traces", headers={"Authorization": f"Bearer {master_key}"}).json()
    assert set(t["trace_id"] for t in traces_m) >= {"tr-alpha-1", "tr-beta-1"}


def test_migration_7_adds_tenant_ownership_and_leases(tmp_path: Path):
    """Verifies Migration 7 upgrades legacy databases smoothly and sets default project ownership."""
    import sqlite3

    legacy_db_file = tmp_path / "legacy_v6.db"
    conn = sqlite3.connect(str(legacy_db_file))
    conn.execute("""
        CREATE TABLE schema_migrations (
            version INTEGER PRIMARY KEY,
            applied_at TEXT NOT NULL,
            description TEXT NOT NULL
        )
    """)
    for v in range(1, 7):
        conn.execute(f"INSERT INTO schema_migrations VALUES ({v}, '2026-01-01', 'v{v}')")

    # Create pre-migration run_jobs and plan_approvals without project_id
    conn.execute("""
        CREATE TABLE run_jobs (
            job_id TEXT PRIMARY KEY,
            plan_id TEXT NOT NULL,
            run_id TEXT,
            status TEXT NOT NULL,
            total_cases INTEGER NOT NULL DEFAULT 0,
            completed_cases INTEGER NOT NULL DEFAULT 0,
            failed_cases INTEGER NOT NULL DEFAULT 0,
            booked_spend_usd TEXT,
            error_message TEXT,
            cancelled INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            finished_at TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE plan_approvals (
            plan_id TEXT PRIMARY KEY,
            fingerprint TEXT NOT NULL,
            summary_json TEXT NOT NULL,
            status TEXT NOT NULL,
            requested_by TEXT NOT NULL,
            created_at REAL NOT NULL,
            expires_at REAL NOT NULL,
            approved_by TEXT,
            approved_at REAL
        )
    """)
    conn.execute("""
        INSERT INTO run_jobs (job_id, plan_id, status, created_at, updated_at)
        VALUES ('job-legacy-1', 'plan-legacy-1', 'completed', '2026-01-01T00:00:00Z', '2026-01-01T00:00:00Z')
    """)
    conn.execute("""
        INSERT INTO plan_approvals (plan_id, fingerprint, summary_json, status, requested_by, created_at, expires_at)
        VALUES ('plan-legacy-1', 'fp-legacy', '{}', 'PENDING', 'dev', 1000.0, 2000.0)
    """)
    conn.commit()
    conn.close()

    # Run DatabaseManager.init_db() which applies migration 7
    mgr = DatabaseManager(legacy_db_file)
    mgr.init_db()

    with mgr.get_connection() as c:
        # Verify schema version 7 is present
        versions = [r[0] for r in c.execute("SELECT version FROM schema_migrations ORDER BY version").fetchall()]
        assert 7 in versions

        # Verify run_jobs has project_id and lease columns
        job_cols = {r[1]: r[2] for r in c.execute("PRAGMA table_info(run_jobs)").fetchall()}
        assert "project_id" in job_cols
        assert "worker_id" in job_cols
        assert "lease_expires_at" in job_cols
        assert "heartbeat_at" in job_cols
        assert "attempt_count" in job_cols

        # Verify existing legacy job has default project_id
        job_row = c.execute("SELECT job_id, project_id FROM run_jobs WHERE job_id = 'job-legacy-1'").fetchone()
        assert job_row[0] == "job-legacy-1"
        assert job_row[1] == "default"

        # Verify plan_approvals has project_id
        plan_cols = {r[1]: r[2] for r in c.execute("PRAGMA table_info(plan_approvals)").fetchall()}
        assert "project_id" in plan_cols

        # Verify existing legacy plan approval has default project_id
        plan_row = c.execute("SELECT plan_id, project_id FROM plan_approvals WHERE plan_id = 'plan-legacy-1'").fetchone()
        assert plan_row[0] == "plan-legacy-1"
        assert plan_row[1] == "default"

"""Unit tests for Milestone 3 - Phase 1 & 2: Versioned REST API v1, Asynchronous Jobs & Scoped Authentication.

Tests:
1. Target, dataset, plan, run, budget, and trace endpoints under `/api/v1/`.
2. Standard error envelopes with stable error codes (approval_required, approval_invalid, forbidden, unauthorized, not_found).
3. Asynchronous job execution model (HTTP 202 Accepted, job state polling, cooperative cancellation).
4. Scoped API key authentication and authorization enforcement.
5. OpenAPI 3.1 specification completeness for v1 routes.
"""

from datetime import datetime, timezone, timedelta
import json
from pathlib import Path
import time
import pytest
from fastapi.testclient import TestClient

from runport.api.app import create_app
from runport.api.v1.auth import (
    SCOPE_DATASETS_READ,
    SCOPE_PLANS_APPROVE,
    SCOPE_PLANS_CREATE,
    SCOPE_RUNS_EXECUTE,
    SCOPE_RUNS_READ,
    SCOPE_TARGETS_READ,
    hash_api_key,
)
from runport.core.config import settings
from runport.storage.db import DatabaseManager
from runport.traces.domain import Span, SpanKind, SpanStatus, Trace
from runport.traces.repository import TraceRepository


@pytest.fixture
def test_env(tmp_path: Path, monkeypatch):
    """Sets up an isolated database and dataset environment for API v1 testing."""
    db_file = tmp_path / "v1_test.db"
    monkeypatch.setattr(type(settings), "db_path", property(lambda self: db_file))

    # Set up mock evaluation dataset directory
    eval_dir = tmp_path / "data" / "evaluation"
    eval_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(settings, "workspace_root", tmp_path)

    # Create sample dataset with valid privacy classification (PUBLIC)
    sample_dataset = eval_dir / "test_dataset.jsonl"
    with open(sample_dataset, "w", encoding="utf-8") as f:
        f.write('{"id": "case-01", "query": "What is Python?", "expected_answer": "A programming language", "classification": "PUBLIC"}\n')
        f.write('{"id": "case-02", "query": "What is 2+2?", "expected_answer": "4", "classification": "PUBLIC"}\n')

    db = DatabaseManager(db_file)
    db.init_db()

    # Seed catalog models
    from decimal import Decimal
    from runport.models.catalog import ModelCandidate, seed_default_portfolio
    seed_default_portfolio(
        db,
        [
            ModelCandidate(
                model_id="google/gemini-3.5-flash-lite",
                display_name="Gemini 3.5 Flash Lite",
                provider="google",
                deployment_mode="HOSTED_DIRECT",
                license="Proprietary Commercial API",
                context_length=1000000,
                input_price_per_1m_usd=Decimal("0.0750"),
                output_price_per_1m_usd=Decimal("0.3000"),
                verification_status="UNVERIFIED_CATALOG_ENTRY",
                experimental_purpose="High-throughput multimodal baseline for evaluation triage.",
            ),
            ModelCandidate(
                model_id="openai/gpt-4o-mini",
                display_name="GPT-4o Mini",
                provider="openai",
                deployment_mode="HOSTED_OPENROUTER",
                license="Proprietary Commercial API",
                context_length=128000,
                input_price_per_1m_usd=Decimal("0.1500"),
                output_price_per_1m_usd=Decimal("0.6000"),
                verification_status="UNVERIFIED_CATALOG_ENTRY",
                experimental_purpose="Compact commercial frontier candidate.",
            ),
        ],
    )

    # Create linked evaluation run for trace FK
    t0 = datetime(2026, 11, 8, 10, 0, 0, tzinfo=timezone.utc)
    db.save_evaluation_run(
        {
            "run_id": "run-v1-existing",
            "timestamp": t0.isoformat(),
            "model_id": "google/gemini-3.5-flash-lite",
            "dataset_path": "test_dataset.jsonl",
            "total_cases": 2,
            "completed_cases": 2,
            "failed_cases": 0,
            "duration_ms": 120.0,
            "total_cost_usd": "0.00001",
        }
    )

    # Insert sample result
    db.save_evaluation_results(
        [
            {
                "result_id": "res-01",
                "run_id": "run-v1-existing",
                "case_id": "case-01",
                "prompt": "What is Python?",
                "generated_output": "A programming language",
                "latency_ms": 60.0,
                "prompt_tokens": 10,
                "completion_tokens": 5,
                "cost_usd": "0.000005",
                "cost_basis": "ESTIMATED",
                "accuracy": 1.0,
                "score_kind": "ground_truth",
                "trace_id": "tr-v1-01",
            }
        ]
    )

    app = create_app()
    client = TestClient(app)
    return {"client": client, "db": db, "dataset_file": sample_dataset}


# =============================================================================
# 1. Target & Dataset Endpoints
# =============================================================================


def test_v1_targets_endpoints(test_env):
    client = test_env["client"]

    # List targets
    res = client.get("/api/v1/targets")
    assert res.status_code == 200
    targets = res.json()
    assert isinstance(targets, list)
    assert len(targets) > 0

    target_id = targets[0]["target_id"]

    # Get single target
    res_one = client.get(f"/api/v1/targets/{target_id}")
    assert res_one.status_code == 200
    assert res_one.json()["target_id"] == target_id

    # 404 for unknown target
    res_404 = client.get("/api/v1/targets/non-existent-target")
    assert res_404.status_code == 404
    assert res_404.json()["error"]["code"] == "not_found"


def test_v1_datasets_endpoints(test_env):
    client = test_env["client"]

    # List datasets
    res = client.get("/api/v1/datasets")
    assert res.status_code == 200
    datasets = res.json()
    assert len(datasets) == 1
    assert datasets[0]["filename"] == "test_dataset.jsonl"
    assert datasets[0]["case_count"] == 2

    # Get single dataset
    res_one = client.get("/api/v1/datasets/test_dataset.jsonl")
    assert res_one.status_code == 200
    assert res_one.json()["case_count"] == 2

    # Upload new dataset
    content = b'{"id": "up-01", "query": "hello"}\n'
    res_up = client.post(
        "/api/v1/datasets",
        files={"file": ("uploaded.jsonl", content, "application/json")},
    )
    assert res_up.status_code == 200
    assert res_up.json()["filename"] == "uploaded.jsonl"
    assert res_up.json()["case_count"] == 1


# =============================================================================
# 2. Plan Creation, Inspection, and Approval
# =============================================================================


def test_v1_plan_lifecycle_and_error_envelopes(test_env):
    client = test_env["client"]

    # 1. Create plan
    plan_payload = {
        "target_ids": ["google/gemini-3.5-flash-lite"],
        "dataset_name": "test_dataset.jsonl",
        "sample_size": 2,
    }
    res_plan = client.post("/api/v1/plans", json=plan_payload)
    assert res_plan.status_code == 200
    plan_data = res_plan.json()
    assert plan_data["status"] == "PENDING"
    assert "plan_id" in plan_data
    assert "plan_fingerprint" in plan_data
    fingerprint = plan_data["plan_fingerprint"]
    plan_id = plan_data["plan_id"]

    # 2. Inspect plan
    res_get = client.get(f"/api/v1/plans/{plan_id}")
    assert res_get.status_code == 200
    assert res_get.json()["plan_id"] == plan_id

    # 3. Attempt to run unapproved plan -> 428 ApprovalRequiredError
    res_unapproved_run = client.post(f"/api/v1/plans/{plan_id}/runs")
    assert res_unapproved_run.status_code == 428
    err = res_unapproved_run.json()["error"]
    assert err["code"] == "approval_required"

    # 4. Attempt to approve with invalid fingerprint -> 403 ApprovalInvalidError
    res_bad_approve = client.post(
        f"/api/v1/plans/{plan_id}/approve",
        json={"fingerprint": "invalid_wrong_fingerprint_hash"},
    )
    assert res_bad_approve.status_code == 403
    assert res_bad_approve.json()["error"]["code"] == "approval_invalid"

    # 5. Approve with correct fingerprint
    res_approve = client.post(
        f"/api/v1/plans/{plan_id}/approve",
        json={"fingerprint": fingerprint, "approver": "Test Suite"},
    )
    assert res_approve.status_code == 200
    assert res_approve.json()["status"] == "APPROVED"
    assert "Test Suite" in res_approve.json()["approved_by"]


# =============================================================================
# 3. Asynchronous Job Execution & Cancellation
# =============================================================================


def test_v1_async_job_submission_and_status(test_env):
    client = test_env["client"]

    # Create and approve a plan
    plan_res = client.post(
        "/api/v1/plans",
        json={"target_ids": ["google/gemini-3.5-flash-lite"], "dataset_name": "test_dataset.jsonl", "sample_size": 1},
    ).json()
    client.post(
        f"/api/v1/plans/{plan_res['plan_id']}/approve",
        json={"fingerprint": plan_res["plan_fingerprint"]},
    )

    # Submit run -> HTTP 202 Accepted
    res_run = client.post(f"/api/v1/plans/{plan_res['plan_id']}/runs")
    assert res_run.status_code == 202
    job_data = res_run.json()
    assert "job_id" in job_data
    assert job_data["status"] in ("queued", "running", "completed")
    job_id = job_data["job_id"]

    # Inspect job status via GET /api/v1/jobs/{job_id}
    res_job = client.get(f"/api/v1/jobs/{job_id}")
    assert res_job.status_code == 200
    assert res_job.json()["job_id"] == job_id


def test_v1_job_cancellation(test_env):
    client = test_env["client"]

    # Create and approve plan
    plan_res = client.post(
        "/api/v1/plans",
        json={"target_ids": ["google/gemini-3.5-flash-lite"], "dataset_name": "test_dataset.jsonl"},
    ).json()
    client.post(
        f"/api/v1/plans/{plan_res['plan_id']}/approve",
        json={"fingerprint": plan_res["plan_fingerprint"]},
    )

    # Submit job
    job = client.post(f"/api/v1/plans/{plan_res['plan_id']}/runs").json()
    job_id = job["job_id"]

    # Cancel job
    res_cancel = client.post(f"/api/v1/jobs/{job_id}/cancel")
    assert res_cancel.status_code == 200
    assert res_cancel.json()["cancelled"] is True


# =============================================================================
# 4. Runs Inspection & Results
# =============================================================================


def test_v1_runs_and_results(test_env):
    client = test_env["client"]

    # List runs
    res = client.get("/api/v1/runs")
    assert res.status_code == 200
    runs = res.json()
    assert len(runs) >= 1
    assert runs[0]["run_id"] == "run-v1-existing"

    # Get single run
    res_run = client.get("/api/v1/runs/run-v1-existing")
    assert res_run.status_code == 200
    assert res_run.json()["model_id"] == "google/gemini-3.5-flash-lite"

    # Get run results
    res_results = client.get("/api/v1/runs/run-v1-existing/results")
    assert res_results.status_code == 200
    data = res_results.json()
    assert data["total_cases"] == 1
    assert data["results"][0]["case_id"] == "case-01"
    assert data["results"][0]["accuracy"] == 1.0


# =============================================================================
# 5. Budget & Traces Endpoints
# =============================================================================


def test_v1_budget_status(test_env):
    client = test_env["client"]
    res = client.get("/api/v1/budget")
    assert res.status_code == 200
    data = res.json()
    assert "policy" in data
    assert "spend" in data
    assert "unresolved_count" in data


def test_v1_traces_ingest_and_get(test_env):
    client = test_env["client"]
    db = test_env["db"]

    otlp_payload = {
        "resourceSpans": [
            {
                "scopeSpans": [
                    {
                        "spans": [
                            {
                                "traceId": "v1-trace-42",
                                "spanId": "v1-span-42",
                                "name": "chat_step",
                                "kind": 3,
                                "attributes": [
                                    {"key": "openinference.span.kind", "value": {"stringValue": "LLM"}},
                                    {"key": "runport.run_id", "value": {"stringValue": "run-v1-existing"}},
                                ],
                                "status": {"code": 1},
                            }
                        ]
                    }
                ]
            }
        ]
    }

    # Ingest
    res_post = client.post("/api/v1/traces", json=otlp_payload)
    assert res_post.status_code == 200
    assert res_post.json()["status"] == "ok"

    # Get trace
    res_get = client.get("/api/v1/traces/v1-trace-42")
    assert res_get.status_code == 200
    assert res_get.json()["trace_id"] == "v1-trace-42"

    # Export OTLP
    res_otlp = client.get("/api/v1/traces/v1-trace-42/otlp")
    assert res_otlp.status_code == 200
    assert "resourceSpans" in res_otlp.json()


# =============================================================================
# 6. Scoped API Key Authentication & Authorization
# =============================================================================


def test_v1_scoped_api_key_enforcement(test_env):
    client = test_env["client"]
    db = test_env["db"]

    # Create an API key with ONLY targets:read scope
    raw_key = "rp_key123_secretabc456"
    db.create_api_key(
        key_id="key123",
        key_hash=hash_api_key(raw_key),
        name="ReadOnlyTargets",
        scopes=[SCOPE_TARGETS_READ],
    )

    headers = {"Authorization": f"Bearer {raw_key}"}

    # 1. targets:read endpoint succeeds
    res_allowed = client.get("/api/v1/targets", headers=headers)
    assert res_allowed.status_code == 200

    # 2. plans:create endpoint is forbidden (403)
    res_forbidden = client.post(
        "/api/v1/plans",
        headers=headers,
        json={"target_ids": ["google/gemini-3.5-flash-lite"], "dataset_name": "test_dataset.jsonl"},
    )
    assert res_forbidden.status_code == 403
    assert res_forbidden.json()["error"]["code"] == "forbidden"

    # 3. Invalid key returns 401 Unauthorized
    bad_headers = {"Authorization": "Bearer rp_fake_invalid_key"}
    res_unauth = client.get("/api/v1/targets", headers=bad_headers)
    assert res_unauth.status_code == 401
    assert res_unauth.json()["error"]["code"] == "unauthorized"

    # 4. Revoked key returns 401 Unauthorized
    db.revoke_api_key("key123")
    res_revoked = client.get("/api/v1/targets", headers=headers)
    assert res_revoked.status_code == 401
    assert res_revoked.json()["error"]["code"] == "unauthorized"


# =============================================================================
# 7. OpenAPI Schema Validation
# =============================================================================


def test_v1_openapi_schema(test_env):
    client = test_env["client"]
    res = client.get("/api/openapi.json")
    assert res.status_code == 200
    schema = res.json()

    paths = schema.get("paths", {})
    # Verify core v1 routes exist in the OpenAPI definition
    assert "/api/v1/targets" in paths
    assert "/api/v1/datasets" in paths
    assert "/api/v1/plans" in paths
    assert "/api/v1/plans/{plan_id}" in paths
    assert "/api/v1/plans/{plan_id}/approve" in paths
    assert "/api/v1/plans/{plan_id}/runs" in paths
    assert "/api/v1/jobs/{job_id}" in paths
    assert "/api/v1/runs" in paths
    assert "/api/v1/budget" in paths
    assert "/api/v1/traces" in paths

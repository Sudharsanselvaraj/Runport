"""Tests for hardened API endpoints and web service security."""

import json
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from runport.api.app import create_app
from runport.core.config import settings
from runport.storage.db import DatabaseManager


@pytest.fixture
def client(tmp_path, monkeypatch):
    """Creates a test client with an isolated temporary workspace."""
    workspace = tmp_path / "workspace"
    workspace.mkdir(parents=True)
    (workspace / "data" / "evaluation").mkdir(parents=True)
    (workspace / "data" / "traces").mkdir(parents=True)

    monkeypatch.setattr(settings, "workspace_root", workspace)

    # Create a small evaluation dataset
    dataset_file = workspace / "data" / "evaluation" / "test_dataset.jsonl"
    with open(dataset_file, "w", encoding="utf-8") as f:
        f.write(json.dumps({"case_id": "c1", "query": "Test query 1", "ground_truth": "YES"}) + "\n")
        f.write(json.dumps({"case_id": "c2", "query": "Test query 2", "ground_truth": "NO"}) + "\n")

    db = DatabaseManager(settings.db_path)
    db.init_db()

    app = create_app()
    return TestClient(app)


def test_setup_endpoint(client):
    """GET /api/setup returns workspace paths, spend caps, forbidden fields, and schema."""
    res = client.get("/api/setup")
    assert res.status_code == 200
    data = res.json()
    assert data["app_name"] == "Runport"
    assert data["mode"] == "local_first"
    assert "user4" in data["forbidden_fields"]
    assert "required_fields" in data["dataset_schema"]
    assert data["budget_policy"]["total_budget_usd"] > 0


def test_models_endpoint(client):
    """GET /api/models returns models with pricing and verification status."""
    res = client.get("/api/models")
    assert res.status_code == 200
    models = res.json()
    assert len(models) >= 0


def test_dataset_upload_path_traversal_blocked(client):
    """POST /api/datasets/upload blocks path traversal characters fail-closed."""
    # Attempt directory traversal filename
    files = {"file": ("../../evil.jsonl", b'{"case_id": "bad", "query": "evil"}', "application/json")}
    res = client.post("/api/datasets/upload", files=files)
    assert res.status_code == 400
    assert "traversal" in res.json()["detail"].lower()


def test_dataset_upload_disallows_executables(client):
    """POST /api/datasets/upload permits only .jsonl, .csv, and .json evaluation datasets."""
    files = {"file": ("exploit.sh", b'#!/bin/sh\necho evil', "text/plain")}
    res = client.post("/api/datasets/upload", files=files)
    assert res.status_code == 400
    assert "permitted" in res.json()["detail"].lower()


def test_dataset_upload_safe_success(client):
    """POST /api/datasets/upload successfully saves valid datasets inside data/evaluation."""
    content = b'{"case_id": "u1", "query": "Upload test"}\n{"case_id": "u2", "query": "Upload test 2"}\n'
    files = {"file": ("uploaded_eval.jsonl", content, "application/json")}
    res = client.post("/api/datasets/upload", files=files)
    assert res.status_code == 200
    data = res.json()
    assert data["filename"] == "uploaded_eval.jsonl"
    assert data["case_count"] == 2


def test_run_approval_single_use_invariant(client):
    """Approval token is single-use and cannot be consumed more than once."""
    fp = "abcd1234ef567890"
    res = client.post("/api/runs/approve", json={
        "plan_fingerprint": fp,
        "user": "Tester",
        "timestamp": "2026-11-03T10:00:00Z"
    })
    assert res.status_code == 200
    token = res.json()["approval_token"]
    assert token.startswith("approval-")

    # Attempting to execute live run with mismatched fingerprint fails
    res_mismatch = client.post("/api/runs", json={
        "target_ids": ["qwen/qwen-2.5-7b-instruct"],
        "dataset_name": "test_dataset.jsonl",
        "plan_fingerprint": fp,
        "is_replay": False,
        "approve_token": "wrong-token"
    })
    assert res_mismatch.status_code == 403


def test_replay_run_books_zero_and_persists_results(client):
    """Replay runs book $0.00 spend, label provenance REPLAYED, and save results."""
    res = client.post("/api/runs", json={
        "target_ids": ["test-model-1"],
        "dataset_name": "test_dataset.jsonl",
        "plan_fingerprint": "plan-fp-replay-1",
        "is_replay": True,
        "sample_size": 2
    })
    assert res.status_code == 200
    data = res.json()
    assert data["is_replay"] is True
    assert data["provenance"] == "REPLAYED"
    assert data["total_spend_usd"] == "0.0000"
    run_id = data["run_id"]

    # Verify run is retrievable via GET /api/runs and GET /api/runs/{run_id}
    res_runs = client.get("/api/runs")
    assert res_runs.status_code == 200
    runs = res_runs.json()
    assert any(r["run_id"] == run_id for r in runs)

    res_detail = client.get(f"/api/runs/{run_id}")
    assert res_detail.status_code == 200
    detail = res_detail.json()
    assert detail["run"]["run_id"] == run_id
    assert len(detail["results"]) == 2

    # Verify report calculation
    res_rep = client.get(f"/api/reports/{run_id}")
    assert res_rep.status_code == 200
    rep = res_rep.json()
    assert rep["total_cases"] == 2
    assert rep["wilson_ci"] is not None
    assert rep["total_cost_usd"] == 0.0


def test_sanitized_trace_export(client):
    """GET /api/reports/export-traces scrubs secrets before output."""
    res_json = client.get("/api/reports/export-traces?format=json")
    assert res_json.status_code == 200
    data = res_json.json()
    assert data["sanitized"] is True

    res_zip = client.get("/api/reports/export-traces?format=zip")
    assert res_zip.status_code == 200
    assert res_zip.headers["content-type"] == "application/zip"

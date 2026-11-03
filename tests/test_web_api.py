"""Unit tests for the Runport FastAPI backend API."""

import json
from decimal import Decimal
import pytest
from fastapi.testclient import TestClient

from runport.api.app import create_app
from runport.targets import TargetStatus


@pytest.fixture
def client():
    app = create_app()
    return TestClient(app)


def test_health_check(client):
    res = client.get("/api/health")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "ok"
    assert data["app"] == "runport"


def test_list_targets(client):
    res = client.get("/api/targets")
    assert res.status_code == 200
    targets = res.json()
    assert isinstance(targets, list)
    assert len(targets) > 0
    # Check that a catalog model is present
    model_ids = [t["target_id"] for t in targets]
    assert "google/gemini-3.5-flash-lite" in model_ids


def test_test_target_http(client, monkeypatch):
    class FakeResp:
        def read(self):
            return json.dumps({"output": "Workflow response from test"}).encode()

        def close(self):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

    monkeypatch.setattr("urllib.request.urlopen", lambda req, timeout=None: FakeResp())

    payload = {
        "target": {
            "target_id": "test-http",
            "name": "Test HTTP Target",
            "target_type": "workflow_http",
            "url": "https://api.example.com/test",
        },
        "input_payload": {"query": "test query"},
    }
    res = client.post("/api/targets/test", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["is_success"] is True
    assert data["output_text"] == "Workflow response from test"


def test_list_datasets(client):
    res = client.get("/api/datasets")
    assert res.status_code == 200
    datasets = res.json()
    assert isinstance(datasets, list)
    filenames = [d["filename"] for d in datasets]
    assert "synthetic_seed_eval.jsonl" in filenames


def test_get_dataset_detail(client):
    res = client.get("/api/datasets/synthetic_seed_eval.jsonl")
    assert res.status_code == 200
    data = res.json()
    assert data["filename"] == "synthetic_seed_eval.jsonl"
    assert data["total_cases"] > 0
    assert len(data["cases_preview"]) > 0


def test_get_budget(client):
    res = client.get("/api/budget")
    assert res.status_code == 200
    data = res.json()
    assert "policy" in data
    assert "spend" in data
    assert data["policy"]["require_priced"] is False


def test_create_plan_and_fingerprint(client):
    payload = {
        "target_ids": ["google/gemini-3.5-flash-lite"],
        "dataset_name": "synthetic_seed_eval.jsonl",
        "sample_size": 5,
    }
    res = client.post("/api/plan", json=payload)
    assert res.status_code == 200
    plan = res.json()
    assert "plan_fingerprint" in plan
    assert len(plan["plan_fingerprint"]) == 16
    assert plan["projected_cases"] == 5
    assert plan["projected_cost_usd"] >= 0.0
    assert "RUN LIVE" in plan["expected_confirmation_phrase"]


def test_execute_run_replay(client):
    payload = {
        "target_ids": ["google/gemini-3.5-flash-lite"],
        "dataset_name": "synthetic_seed_eval.jsonl",
        "sample_size": 3,
        "plan_fingerprint": "mock_fp",
        "is_replay": True,
    }
    res = client.post("/api/runs", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["is_replay"] is True
    assert data["provenance"] == "REPLAYED"
    assert data["total_spend_usd"] == "0.0000"
    assert data["cases_evaluated"] == 3


def test_execute_run_live_requires_approval(client):
    payload = {
        "target_ids": ["google/gemini-3.5-flash-lite"],
        "dataset_name": "synthetic_seed_eval.jsonl",
        "sample_size": 3,
        "plan_fingerprint": "fake_fingerprint",
        "is_replay": False,
    }
    res = client.post("/api/runs", json=payload)
    # Fail closed: no approval token
    assert res.status_code == 403


def test_execute_run_live_rejects_mismatched_token(client):
    payload = {
        "target_ids": ["google/gemini-3.5-flash-lite"],
        "dataset_name": "synthetic_seed_eval.jsonl",
        "sample_size": 3,
        "plan_fingerprint": "fake_fingerprint",
        "approve_token": "wrong_token",
        "is_replay": False,
    }
    res = client.post("/api/runs", json=payload)
    # Fail closed: mismatched token
    assert res.status_code == 403

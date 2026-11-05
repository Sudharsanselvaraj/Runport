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


class _FakeWorkflowResp:
    def read(self):
        return json.dumps({"output": "Workflow response from test"}).encode()

    def close(self):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass


def _http_target_payload(query="test query", **target_overrides):
    target = {
        "target_id": "test-http",
        "name": "Test HTTP Target",
        "target_type": "workflow_http",
        "url": "https://api.example.com/test",
        "pricing": {"fixed_usd_per_request": "0.001"},
    }
    target.update(target_overrides)
    return {"target": target, "input_payload": {"query": query}}


@pytest.fixture
def fake_workflow(monkeypatch):
    calls = []

    def fake_urlopen(req, timeout=None):
        calls.append(req.full_url)
        return _FakeWorkflowResp()

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    return calls


def _ledger():
    from runport.core.config import settings
    from runport.storage.db import DatabaseManager

    db = DatabaseManager(settings.db_path)
    db.init_db()
    return db.get_recent_transactions(limit=50)


def _plan(client, body):
    res = client.post("/api/targets/test", json=body)
    assert res.status_code == 428, res.text
    d = res.json()["detail"]
    return d["plan_fingerprint"], d["plan_nonce"]


def test_test_target_without_approval_sends_nothing(client, fake_workflow):
    res = client.post("/api/targets/test", json=_http_target_payload())
    assert res.status_code == 428
    detail = res.json()["detail"]
    assert detail["status"] == "approval_required"
    assert len(detail["plan_fingerprint"]) == 64
    assert detail["expected_confirmation_phrase"].endswith(detail["plan_fingerprint"])
    assert fake_workflow == []
    assert _ledger() == []


def test_test_target_http_runs_through_guarded_runner(client, fake_workflow):
    fp, nonce = _plan(client, _http_target_payload())

    res = client.post("/api/targets/test", json={**_http_target_payload(), "approve_token": fp, "plan_nonce": nonce})
    assert res.status_code == 200
    data = res.json()
    assert data["is_success"] is True
    assert data["output_text"] == "Workflow response from test"
    assert data["plan_fingerprint"] == fp
    assert data["cost_basis"] == "ESTIMATED"
    assert len(fake_workflow) == 1

    ledger = _ledger()
    assert len(ledger) == 1 and ledger[0]["run_id"] == data["run_id"]
    assert client.get(f"/api/runs/{data['run_id']}").status_code == 200

    reuse = client.post("/api/targets/test", json={**_http_target_payload(), "approve_token": fp, "plan_nonce": nonce})
    assert reuse.status_code == 428  # the nonce was redeemed; a fresh plan is issued instead
    assert len(fake_workflow) == 1

    # The same target and prompt can be tested again with a new approval.
    fp2, nonce2 = _plan(client, _http_target_payload())
    assert fp2 != fp
    again = client.post("/api/targets/test", json={**_http_target_payload(), "approve_token": fp2, "plan_nonce": nonce2})
    assert again.status_code == 200 and len(fake_workflow) == 2


def test_test_target_accepts_ui_approval_token(client, fake_workflow):
    fp, nonce = _plan(client, _http_target_payload("ui"))
    token = client.post("/api/runs/approve", json={"plan_fingerprint": fp, "timestamp": "2026-11-05T00:00:00Z"}).json()["approval_token"]
    res = client.post("/api/targets/test", json={**_http_target_payload("ui"), "approve_token": token, "plan_nonce": nonce})
    assert res.status_code == 200
    assert len(fake_workflow) == 1


def test_test_target_approval_is_bound_to_target_and_payload(client, fake_workflow):
    fp, nonce = _plan(client, _http_target_payload("first"))
    other_payload = client.post("/api/targets/test", json={**_http_target_payload("second"), "approve_token": fp, "plan_nonce": nonce})
    other_url = client.post(
        "/api/targets/test", json={**_http_target_payload("first", url="https://other.example.com/x"), "approve_token": fp, "plan_nonce": nonce}
    )
    forged_nonce = client.post("/api/targets/test", json={**_http_target_payload("first"), "approve_token": fp, "plan_nonce": "made-up"})
    assert other_payload.status_code == 428 and other_url.status_code == 428 and forged_nonce.status_code == 428
    assert fake_workflow == []


def test_test_target_blocked_by_unresolved_spend(client, fake_workflow):
    from runport.core.budget import BudgetService
    from runport.core.config import settings
    from runport.storage.db import DatabaseManager

    BudgetService(db=DatabaseManager(settings.db_path), policy=settings.budget).record_unresolved_spend("tx-open", "m", "p", "unreconciled")
    fp, nonce = _plan(client, _http_target_payload())
    res = client.post("/api/targets/test", json={**_http_target_payload(), "approve_token": fp, "plan_nonce": nonce})
    assert res.status_code == 403
    assert "Unresolved spend" in res.json()["detail"]
    assert fake_workflow == []


def test_test_target_api_key_never_enters_fingerprint_or_response(client, fake_workflow):
    secret = "sk-test-abcdefghijklmnopqrstuvwxyz"
    body = _http_target_payload(target_type="openai_compat", url="https://api.example.com/v1", model="m", api_key=secret)
    res = client.post("/api/targets/test", json=body)
    assert res.status_code == 428
    assert secret not in res.text


@pytest.mark.parametrize(
    "target_type,extra",
    [("flowise", {"model": "flow-1"}), ("langflow", {"model": "flow-1"}), ("n8n", {}), ("langgraph", {"model": "agent"})],
)
def test_test_target_builds_every_workflow_connector(client, fake_workflow, target_type, extra):
    res = client.post("/api/targets/test", json=_http_target_payload(target_type=target_type, url="https://wf.example.com", **extra))
    assert res.status_code == 428, res.text
    assert fake_workflow == []


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

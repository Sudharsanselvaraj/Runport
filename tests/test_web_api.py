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
    return d["plan_fingerprint"], d["plan_id"]


def _send(client, body, fp, plan_id):
    return client.post("/api/targets/test", json={**body, "approve_token": fp, "plan_id": plan_id})


def test_test_target_without_approval_sends_nothing(client, fake_workflow):
    res = client.post("/api/targets/test", json=_http_target_payload())
    assert res.status_code == 428
    detail = res.json()["detail"]
    assert detail["status"] == "PENDING"
    assert len(detail["plan_fingerprint"]) == 64
    assert detail["plan_id"].startswith("plan-")
    assert detail["expected_confirmation_phrase"].endswith(detail["plan_fingerprint"])
    assert fake_workflow == []
    assert _ledger() == []


def test_test_target_http_runs_through_guarded_runner(client, fake_workflow):
    fp, plan_id = _plan(client, _http_target_payload())

    res = _send(client, _http_target_payload(), fp, plan_id)
    assert res.status_code == 200, res.text
    data = res.json()
    assert data["is_success"] is True
    assert data["output_text"] == "Workflow response from test"
    assert data["plan_fingerprint"] == fp
    assert data["cost_basis"] == "ESTIMATED"
    assert len(fake_workflow) == 1

    ledger = _ledger()
    assert len(ledger) == 1 and ledger[0]["run_id"] == data["run_id"]
    assert client.get(f"/api/runs/{data['run_id']}").status_code == 200

    reuse = _send(client, _http_target_payload(), fp, plan_id)
    assert reuse.status_code == 403  # approval already consumed
    assert len(fake_workflow) == 1

    # The same target and prompt can be tested again with a new plan and approval.
    fp2, plan2 = _plan(client, _http_target_payload())
    assert fp2 != fp
    assert _send(client, _http_target_payload(), fp2, plan2).status_code == 200 and len(fake_workflow) == 2


def test_test_target_unpriced_remote_is_unresolved_not_zero(client, fake_workflow):
    body = _http_target_payload()
    body["target"].pop("pricing")
    fp, plan_id = _plan(client, body)
    data = _send(client, body, fp, plan_id).json()
    assert data["cost_basis"] == "UNRESOLVED" and data["cost_usd"] is None
    assert data["halted_reason"]
    ledger = _ledger()
    assert len(ledger) == 1 and ledger[0]["is_unresolved"] == 1


def test_test_target_localhost_unpriced_books_unavailable(client, fake_workflow):
    body = _http_target_payload(url="http://127.0.0.1:9/agent")
    body["target"].pop("pricing")
    from runport.api.routes import targets as targets_route

    orig = targets_route._build_connector

    def local_ok(t, pricing):
        from runport.connectors.http_workflow import HttpWorkflowConnector

        return HttpWorkflowConnector(target_id=t.target_id, name=t.name, url=t.url, pricing=pricing, allow_localhost=True)

    targets_route._build_connector = local_ok
    try:
        fp, plan_id = _plan(client, body)
        data = _send(client, body, fp, plan_id).json()
    finally:
        targets_route._build_connector = orig
    assert data["cost_basis"] == "UNAVAILABLE" and data["cost_usd"] is None
    assert _ledger()[0]["is_unresolved"] == 0


def test_test_target_approval_is_bound_to_target_and_payload(client, fake_workflow):
    fp, plan_id = _plan(client, _http_target_payload("first"))
    other_payload = _send(client, _http_target_payload("second"), fp, plan_id)
    other_url = _send(client, _http_target_payload("first", url="https://other.example.com/x"), fp, plan_id)
    wrong_fp = _send(client, _http_target_payload("first"), "0" * 64, plan_id)
    unknown_plan = _send(client, _http_target_payload("first"), fp, "plan-doesnotexist")
    for r in (other_payload, other_url, wrong_fp, unknown_plan):
        assert r.status_code == 403, r.text
    assert fake_workflow == []


def test_test_target_blocked_by_unresolved_spend(client, fake_workflow):
    from runport.core.budget import BudgetService
    from runport.core.config import settings
    from runport.storage.db import DatabaseManager

    BudgetService(db=DatabaseManager(settings.db_path), policy=settings.budget).record_unresolved_spend("tx-open", "m", "p", "unreconciled")
    res = client.post("/api/targets/test", json=_http_target_payload())
    detail = res.json()["detail"]
    assert any("unresolved" in b.lower() for b in detail["blockers"])
    approve = _send(client, _http_target_payload(), detail["plan_fingerprint"], detail["plan_id"])
    assert approve.status_code == 403
    assert "blockers" in approve.json()["detail"]
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
    assert len(plan["plan_fingerprint"]) == 64
    assert plan["plan_id"].startswith("plan-") and plan["status"] == "PENDING"
    assert plan["projected_cases"] == 5
    assert plan["projected_cost_usd"] > 0.0
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


def test_approving_an_unknown_fingerprint_is_refused(client):
    res = client.post("/api/runs/approve", json={"plan_fingerprint": "abcd" * 16, "user": "Tester", "timestamp": "2026-11-05T00:00:00Z"})
    assert res.status_code == 404


def test_live_api_run_executes_through_execution_service(client, fake_workflow, monkeypatch):
    """POST /api/plan -> /api/runs/approve -> /api/runs executes a workspace target via GenericRunner and books spend."""
    from runport.core.workspace import BudgetConfig, TargetConfig, WorkspaceConfig

    ws = WorkspaceConfig(
        budget=BudgetConfig(),
        targets=[
            TargetConfig(
                id="support-agent",
                type="http_workflow",
                endpoint="https://agent.example.com/chat",
                options={"pricing": {"fixed_usd_per_request": "0.002"}},
            )
        ],
    )
    monkeypatch.setattr("runport.services.execution.load_workspace_config", lambda: ws)

    plan = client.post("/api/plan", json={"target_ids": ["support-agent"], "dataset_name": "synthetic_seed_eval.jsonl", "sample_size": 2}).json()
    assert plan["is_permitted"] and fake_workflow == []

    body = {
        "target_ids": ["support-agent"],
        "dataset_name": "synthetic_seed_eval.jsonl",
        "sample_size": 2,
        "plan_fingerprint": plan["plan_fingerprint"],
        "is_replay": False,
    }
    unapproved = client.post("/api/runs", json={**body, "approve_token": plan["plan_id"]})
    assert unapproved.status_code == 403 and fake_workflow == []

    token = client.post("/api/runs/approve", json={"plan_fingerprint": plan["plan_fingerprint"], "user": "Tester", "timestamp": "t"}).json()["approval_token"]
    res = client.post("/api/runs", json={**body, "approve_token": token})
    assert res.status_code == 200, res.text
    data = res.json()
    assert data["status"] == "completed" and data["provenance"] == "LIVE"
    assert data["runs"][0]["successful_cases"] == 2
    assert len(fake_workflow) == 2
    assert len(_ledger()) == 2

    again = client.post("/api/runs", json={**body, "approve_token": token})
    assert again.status_code == 403 and len(fake_workflow) == 2


def test_list_targets_includes_workspace_targets_without_secrets(client, monkeypatch):
    from runport.core.workspace import TargetConfig, WorkspaceConfig

    ws = WorkspaceConfig(
        targets=[
            TargetConfig(id="agent", type="http_workflow", endpoint="https://agent.example.com/x", headers={"Authorization": "Bearer ${AGENT_TOKEN}"}),
            TargetConfig(id="local", type="http_workflow", endpoint="http://127.0.0.1:9/x"),
        ]
    )
    monkeypatch.setattr("runport.services.execution.load_workspace_config", lambda: ws)
    monkeypatch.setenv("AGENT_TOKEN", "very-secret-agent-token")
    data = client.get("/api/targets").json()
    by_id = {t["target_id"]: t for t in data if t.get("source") == "workspace"}
    assert by_id["agent"]["billing"] == "billable" and by_id["agent"]["header_names"] == ["Authorization"]
    assert by_id["local"]["billing"] == "local"
    assert "very-secret-agent-token" not in json.dumps(data) and "AGENT_TOKEN" not in json.dumps(data)

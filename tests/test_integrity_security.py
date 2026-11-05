"""Regression tests for the integrity and security remediation.

1. Unknown cost from a possibly billable target is booked UNRESOLVED (never $0.00) and halts the run.
2. Remote API access fails closed without RUNPORT_API_TOKEN; tokens are checked exactly; DNS rebinding is refused.
3. Trace telemetry that was not reported stays None.
4. Approvals expire, are single-use under concurrency, bind to the fingerprint, and cannot come from MCP/SDK.
5. ExecutionService refuses anything not approved, and anything that changed after approval.
"""

import json
import threading
import urllib.error
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from runport.connectors.http_workflow import HttpWorkflowConnector
from runport.connectors.mcp import McpToolTarget
from runport.connectors.openrouter import OpenRouterTarget
from runport.connectors.python_target import PythonCallableTarget, SubprocessTarget
from runport.core.approvers import TokenApprover
from runport.core.budget import BudgetService
from runport.core.workspace import BudgetConfig, WorkspaceConfig
from runport.providers.base import LiveNotAuthorizedError
from runport.runs.executor import GenericRunner
from runport.runs.planner import ExecutionPlan
from runport.services.approvals import ApprovalError, ApprovalStore
from runport.services.execution import ExecutionService
from runport.storage.db import DatabaseManager
from runport.targets.base import BillingMode, CostBasis, Target, TargetResult, TargetStatus, TargetType, billing_for_url
from runport.traces.analyzer import TraceDiagnosticAnalyzer
from runport.traces.importer import TraceImporter

# ---------------------------------------------------------------- 1. billing and unknown spend


@pytest.mark.parametrize(
    "url,expected",
    [
        ("http://127.0.0.1:8000/x", BillingMode.LOCAL),
        ("http://localhost:11434", BillingMode.LOCAL),
        ("http://[::1]:9000", BillingMode.LOCAL),
        ("http://agent.localhost/x", BillingMode.LOCAL),
        ("https://api.openai.com/v1", BillingMode.BILLABLE),
        ("http://10.0.0.5/agent", BillingMode.BILLABLE),
    ],
)
def test_billing_is_derived_from_the_url(url, expected):
    assert billing_for_url(url) == expected


def test_billing_declarations_and_local_targets():
    assert billing_for_url("https://my-agent.example.com", BillingMode.UNBILLED) == BillingMode.UNBILLED
    assert PythonCallableTarget("p", "p", func=lambda x: "ok").billing == BillingMode.LOCAL
    assert SubprocessTarget("s", "s", command=["true"]).billing == BillingMode.LOCAL
    assert McpToolTarget("m", "m", command=["x"]).billing == BillingMode.LOCAL
    assert McpToolTarget("m", "m", url="https://mcp.example.com/mcp").billing == BillingMode.BILLABLE
    assert HttpWorkflowConnector("h", "h", url="https://wf.example.com").billing == BillingMode.BILLABLE
    assert HttpWorkflowConnector("h", "h", url="http://127.0.0.1:1/x", allow_localhost=True).billing == BillingMode.LOCAL


class _Fixed(Target):
    def __init__(self, result: TargetResult, billing=BillingMode.BILLABLE):
        super().__init__("t", "t", TargetType.WORKFLOW_HTTP, billing=billing)
        self._result = result
        self.calls = 0

    def execute(self, input_payload, context=None):
        self.calls += 1
        return self._result


def _run(db, target, n_cases=2):
    ws = WorkspaceConfig(budget=BudgetConfig())
    plan = ExecutionPlan(plan_id="p", target_ids=["t"], dataset_path="d", dataset_hash="h", total_cases=n_cases, budget_cap_usd=Decimal("1"), is_live=True)
    runner = GenericRunner(budget_service=BudgetService(db=db, policy=ws.budget.to_budget_policy()), db=db, workspace=ws)
    cases = [{"id": f"c{i}", "classification": "SYNTHETIC", "query": "q"} for i in range(n_cases)]
    return runner.execute_plan(plan, {"t": target}, cases, approver=TokenApprover(plan.fingerprint, enabled=True))[0], BudgetService(
        db=db, policy=ws.budget.to_budget_policy()
    )


def test_failed_billable_call_with_unknown_cost_is_unresolved(tmp_path):
    db = DatabaseManager(tmp_path / "a.db")
    target = _Fixed(TargetResult("t", TargetStatus.TIMEOUT, error_message="timed out"))
    run, budget = _run(db, target)
    assert run.case_results[0].cost_basis == CostBasis.UNRESOLVED
    assert target.calls == 1 and run.skipped_cases == 1
    assert budget.get_status().unresolved_spend_count == 1


def test_unauthorized_or_unsent_requests_are_not_unresolved(tmp_path):
    db = DatabaseManager(tmp_path / "b.db")
    run, budget = _run(db, _Fixed(TargetResult("t", TargetStatus.UNAUTHORIZED, error_code="401")), n_cases=1)
    assert run.case_results[0].cost_basis == CostBasis.UNAVAILABLE
    run2, _ = _run(db, _Fixed(TargetResult("t", TargetStatus.FAILED, request_sent=False)), n_cases=1)
    assert run2.case_results[0].cost_basis == CostBasis.UNAVAILABLE
    assert budget.get_status().unresolved_spend_count == 0


def test_openrouter_target_maps_cost_provenance(monkeypatch):
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    no_key = OpenRouterTarget("google/gemini-3.5-flash-lite").execute({"id": "c", "query": "hi"})
    assert no_key.status == TargetStatus.FAILED and no_key.request_sent is False

    class FakeResp:
        def __init__(self, body):
            self.body = body

        def read(self):
            return self.body

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-v1-" + "x" * 40)
    body = {"choices": [{"message": {"content": "Paris."}, "finish_reason": "stop"}], "usage": {"prompt_tokens": 10, "completion_tokens": 3}}
    monkeypatch.setattr("urllib.request.urlopen", lambda req, timeout=None: FakeResp(json.dumps(body).encode()))
    target = OpenRouterTarget("google/gemini-3.5-flash-lite")
    monkeypatch.setattr("runport.providers.openrouter.registry.synthetic_live_blockers", lambda *a, **k: [])
    ok = target.execute({"id": "c", "query": "Capital of France?"})
    assert ok.status == TargetStatus.SUCCESS, ok.error_message
    assert ok.tokens_in == 10 and ok.tokens_out == 3
    assert ok.cost_basis in (CostBasis.ESTIMATED, CostBasis.ACTUAL) and ok.cost_usd is not None


# ---------------------------------------------------------------- 2. API access policy


def _app(monkeypatch, token=None, allowed=""):
    if token:
        monkeypatch.setenv("RUNPORT_API_TOKEN", token)
    else:
        monkeypatch.delenv("RUNPORT_API_TOKEN", raising=False)
    monkeypatch.setenv("RUNPORT_ALLOWED_HOSTS", allowed)
    from runport.api.app import create_app

    return create_app()


def test_remote_client_is_refused_without_server_token_whatever_it_sends(monkeypatch):
    app = _app(monkeypatch)
    remote = TestClient(app, client=("203.0.113.9", 4444), base_url="http://localhost")
    for headers in ({}, {"Authorization": "Bearer anything"}, {"X-Runport-Token": "secret"}):
        assert remote.get("/api/budget", headers=headers).status_code == 403
    assert remote.get("/api/health").status_code == 200


def test_loopback_without_token_needs_a_loopback_host_header(monkeypatch):
    app = _app(monkeypatch)
    local = TestClient(app, base_url="http://localhost:8000")
    assert local.get("/api/budget").status_code == 200
    rebound = TestClient(app, base_url="http://attacker.example")
    assert rebound.get("/api/budget").status_code == 403
    allowed = TestClient(_app(monkeypatch, allowed="runport.test"), base_url="http://runport.test")
    assert allowed.get("/api/budget").status_code == 200


def test_configured_token_is_required_everywhere_and_compared_exactly(monkeypatch):
    app = _app(monkeypatch, token="correct-horse-battery")
    local = TestClient(app, base_url="http://localhost")
    remote = TestClient(app, client=("198.51.100.7", 1), base_url="http://runport.example.com")
    assert local.get("/api/budget").status_code == 401
    assert remote.get("/api/budget", headers={"Authorization": "Bearer wrong"}).status_code == 401
    assert remote.get("/api/budget", headers={"Authorization": "Bearer correct-horse-battery"}).status_code == 200
    assert remote.get("/api/budget", headers={"X-Runport-Token": "correct-horse-battery"}).status_code == 200


# ---------------------------------------------------------------- 3. traces


def test_trace_telemetry_that_was_not_reported_stays_none():
    t = TraceImporter._parse_dict_to_trace({"id": "t1", "input": "q", "output": "a"})
    assert t.latency_ms is None and t.total_tokens is None and t.prompt_tokens is None and t.completion_tokens is None
    fast = TraceImporter._parse_dict_to_trace({"id": "t2", "input": "q", "output": "a", "latency_ms": 30, "usage": {"total": 0}})
    assert fast.latency_ms == 30.0  # never rescaled as if it were seconds
    assert fast.total_tokens == 0  # a reported zero is kept
    secs = TraceImporter._parse_dict_to_trace({"id": "t3", "input": "q", "output": "a", "latency": 1.5})
    assert secs.latency_ms == 1500.0
    report = TraceDiagnosticAnalyzer().analyze_batch([t, fast, secs])
    assert report.mean_latency_ms == 765.0
    assert report.total_tokens == 0 and report.traces_missing_tokens == 2 and report.traces_missing_latency == 1
    empty = TraceDiagnosticAnalyzer().analyze_batch([t])
    assert empty.mean_latency_ms is None and empty.total_tokens is None


# ---------------------------------------------------------------- 4. approvals


class _Clock:
    def __init__(self):
        self.now = 1_000_000.0

    def __call__(self):
        return self.now


def test_approval_lifecycle_expiry_and_channels(tmp_path):
    clock = _Clock()
    store = ApprovalStore(DatabaseManager(tmp_path / "ap.db"), clock=clock)
    rec = store.register("fp1", {"x": 1}, requested_by="mcp", ttl_s=60)
    for channel in ("mcp", "sdk", "anything"):
        with pytest.raises(ApprovalError, match="cannot approve"):
            store.approve(rec.plan_id, "fp1", channel=channel, approver="agent")
    with pytest.raises(ApprovalError, match="has not been approved"):
        store.consume(rec.plan_id, "fp1")
    with pytest.raises(ApprovalError, match="fingerprint does not match"):
        store.approve(rec.plan_id, "other", channel="web_ui", approver="me")

    clock.now += 61
    with pytest.raises(ApprovalError, match="expired"):
        store.approve(rec.plan_id, "fp1", channel="web_ui", approver="me")

    rec2 = store.register("fp2", {}, requested_by="web_api", ttl_s=60)
    store.approve(rec2.plan_id, "fp2", channel="cli_interactive", approver="me", ttl_s=30)
    clock.now += 31
    with pytest.raises(ApprovalError, match="expired"):
        store.consume(rec2.plan_id, "fp2")


def test_concurrent_consumption_succeeds_exactly_once(tmp_path):
    store = ApprovalStore(DatabaseManager(tmp_path / "race.db"))
    rec = store.register("fp", {}, requested_by="web_api")
    store.approve(rec.plan_id, "fp", channel="web_ui", approver="me")
    wins, losses = [], []
    barrier = threading.Barrier(8)

    def worker():
        barrier.wait()
        try:
            store.consume(rec.plan_id, "fp")
            wins.append(1)
        except ApprovalError:
            losses.append(1)

    threads = [threading.Thread(target=worker) for _ in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert len(wins) == 1 and len(losses) == 7


# ---------------------------------------------------------------- 5. execution service


def test_execution_service_refuses_unapproved_and_changed_plans(tmp_path):
    db = DatabaseManager(tmp_path / "svc.db")
    service = ExecutionService(db=db, workspace=WorkspaceConfig())
    target = PythonCallableTarget("echo", "echo", func=lambda c: c["query"].upper())
    spec = {"type": "python", "callable": "inline:echo"}
    cases = [{"id": "c1", "query": "hi"}]
    plan = service.plan({"echo": target}, {"echo": spec}, cases, dataset_label="t", requested_by="sdk")
    assert plan.projected_max_cost_usd == Decimal("0")  # local: no spend expected

    with pytest.raises(LiveNotAuthorizedError, match="not been approved"):
        service.execute(plan.plan_id, {"echo": target}, {"echo": spec}, cases)

    service.approve(plan.plan_id, plan.fingerprint, channel="cli_interactive", approver="me")
    with pytest.raises(LiveNotAuthorizedError, match="differ from the approved plan"):
        service.execute(plan.plan_id, {"echo": target}, {"echo": spec}, [{"id": "c1", "query": "changed"}])

    out = service.execute(plan.plan_id, {"echo": target}, {"echo": spec}, cases)
    assert out.runs[0].case_results[0].output_text == "HI"
    with pytest.raises(LiveNotAuthorizedError, match="already been used"):
        service.execute(plan.plan_id, {"echo": target}, {"echo": spec}, cases)


def test_unpriced_billable_plan_reserves_the_per_case_ceiling(tmp_path):
    db = DatabaseManager(tmp_path / "res.db")
    ws = WorkspaceConfig(budget=BudgetConfig(per_case_usd=Decimal("0.05")))
    service = ExecutionService(db=db, workspace=ws)
    remote = HttpWorkflowConnector("wf", "wf", url="https://wf.example.com")
    plan = service.plan(
        {"wf": remote}, {"wf": {"type": "http_workflow", "url": "https://wf.example.com"}}, [{"id": 1}, {"id": 2}], dataset_label="d", requested_by="sdk"
    )
    assert plan.projected_max_cost_usd == Decimal("0.10")
    assert plan.per_target[0]["billing"] == "billable"

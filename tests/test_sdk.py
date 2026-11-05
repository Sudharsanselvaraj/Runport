"""Python SDK: same guarded path as every other interface."""

from decimal import Decimal

import pytest

from runport import sdk
from runport.core.workspace import ApproverConfig, WorkspaceConfig
from runport.providers.base import LiveNotAuthorizedError
from runport.services.execution import ExecutionService
from runport.storage.db import DatabaseManager


@pytest.fixture
def service(tmp_path):
    return ExecutionService(db=DatabaseManager(tmp_path / "sdk.db"), workspace=WorkspaceConfig())


def test_benchmark_a_plain_function_without_rewriting_it(service):
    def my_agent(case):
        return f"answer to {case['query']}"

    out = sdk.benchmark(my_agent, [{"id": "a", "query": "x", "expected_answer": "answer to x"}], service=service)
    run = out.runs[0]
    assert run.successful_cases == 1 and run.total_spend_usd == Decimal("0")
    assert run.case_results[0].cost_basis.value == "UNAVAILABLE"
    saved = service.db.get_evaluation_run(run.run_id)
    assert saved["mean_accuracy"] is not None  # scored with the same rubric as the CLI


def test_remote_target_needs_a_person(service):
    from runport.connectors.http_workflow import HttpWorkflowConnector

    remote = HttpWorkflowConnector("wf", "wf", url="https://wf.example.com/run")
    with pytest.raises(LiveNotAuthorizedError):
        sdk.benchmark(remote, [{"id": "a", "query": "x", "classification": "SYNTHETIC"}], service=service)  # no TTY in tests


def test_local_only_channel_cannot_approve_a_remote_plan(service):
    from runport.connectors.http_workflow import HttpWorkflowConnector

    p = sdk.plan(HttpWorkflowConnector("wf", "wf", url="https://wf.example.com/run"), [{"id": "a"}], service=service)
    with pytest.raises(LiveNotAuthorizedError, match="every target"):
        service.approve(p.plan_id, p.fingerprint, channel="local_only", approver="sdk")
    with pytest.raises(LiveNotAuthorizedError, match="every target"):
        service.approvals.approve(p.plan_id, p.fingerprint, channel="local_only", approver="sdk")


def test_ci_token_approval_requires_the_workspace_switch(tmp_path):
    def f(case):
        return "ok"

    off = ExecutionService(db=DatabaseManager(tmp_path / "a.db"), workspace=WorkspaceConfig())
    p = sdk.plan(f, [{"id": "a"}], service=off)
    with pytest.raises(LiveNotAuthorizedError):
        sdk.approve_with_ci_token(p, p.fingerprint)

    on = ExecutionService(db=DatabaseManager(tmp_path / "b.db"), workspace=WorkspaceConfig(approver=ApproverConfig(token_approver_enabled=True)))
    p2 = sdk.plan(f, [{"id": "a"}], service=on)
    with pytest.raises(LiveNotAuthorizedError):
        sdk.approve_with_ci_token(p2, "wrong")
    sdk.approve_with_ci_token(p2, p2.fingerprint)
    assert sdk.execute(p2).runs[0].successful_cases == 1

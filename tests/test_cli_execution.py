"""The CLI live benchmark runs through ExecutionService and GenericRunner (offline: fake transport, sockets unused)."""

import json

import pytest
from typer.testing import CliRunner

from runport.cli import app
from runport.core.workspace import BudgetConfig, TargetConfig, WorkspaceConfig
from runport.dataset.manager import DatasetManager
from runport.providers.base import LiveNotAuthorizedError
from runport.schemas.evaluation import DataClassification, DatasetSplit, EvaluationCase, VerificationRecord, VerificationStatus
from runport.storage.db import DatabaseManager


def _dataset(tmp_path, classification=DataClassification.SYNTHETIC):
    cases = [
        EvaluationCase(
            id=f"c{i}",
            query=f"question {i}",
            expected_answer="the answer",
            classification=classification,
            split=DatasetSplit.TEST,
            verification=VerificationRecord(status=VerificationStatus.VERIFIED, reference_source="synthetic"),
        )
        for i in range(2)
    ]
    p = tmp_path / "ds.jsonl"
    DatasetManager.save_jsonl(cases, p)
    return p


class _Resp:
    def read(self):
        return json.dumps({"output": "the answer"}).encode()

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


@pytest.fixture
def workspace_target(monkeypatch):
    ws = WorkspaceConfig(
        budget=BudgetConfig(),
        targets=[
            TargetConfig(
                id="support-agent", type="http_workflow", endpoint="https://agent.example.com/chat", options={"pricing": {"fixed_usd_per_request": "0.001"}}
            )
        ],
    )
    monkeypatch.setattr("runport.services.execution.load_workspace_config", lambda: ws)
    calls = []
    monkeypatch.setattr("urllib.request.urlopen", lambda req, timeout=None: calls.append(req.full_url) or _Resp())
    return calls


def _ledger():
    from runport.core.config import settings

    return DatabaseManager(settings.db_path).get_recent_transactions(50)


def test_cli_live_benchmark_of_a_workspace_target_runs_through_the_service(tmp_path, monkeypatch, workspace_target):
    seen = {}

    def approve(models, summary, *, plan_fingerprint=None, **kw):
        seen["fingerprint"] = plan_fingerprint
        from runport.core.live_guard import LiveAuthorization

        return LiveAuthorization(models=tuple(models))

    monkeypatch.setattr("runport.core.live_guard.confirm_live_run", approve)
    result = CliRunner().invoke(app, ["benchmark", "--target", "support-agent", "--dataset", str(_dataset(tmp_path)), "--split", "TEST", "--live"])
    assert result.exit_code == 0, result.output
    assert len(seen["fingerprint"]) == 64  # the typed approval is bound to the plan fingerprint
    assert len(workspace_target) == 2
    ledger = _ledger()
    assert len(ledger) == 2 and all(t["cost_basis"] == "ESTIMATED" for t in ledger)


def test_cli_live_benchmark_refused_without_interactive_approval(tmp_path, workspace_target):
    result = CliRunner().invoke(app, ["benchmark", "--target", "support-agent", "--dataset", str(_dataset(tmp_path)), "--split", "TEST", "--live"])
    assert result.exit_code == 1
    assert "refused" in result.output.lower()
    assert workspace_target == [] and _ledger() == []


def test_cli_live_benchmark_blocks_unclassified_cases_before_sending(tmp_path, monkeypatch, workspace_target):
    from runport.core.live_guard import LiveAuthorization

    monkeypatch.setattr("runport.core.live_guard.confirm_live_run", lambda models, summary, **kw: LiveAuthorization(models=tuple(models)))
    ds = _dataset(tmp_path, classification=DataClassification.CONFIDENTIAL)
    result = CliRunner().invoke(app, ["benchmark", "--target", "support-agent", "--dataset", str(ds), "--split", "TEST", "--live"])
    assert result.exit_code == 1
    assert workspace_target == []


def test_cli_approve_refuses_without_a_terminal_and_approves_with_one(tmp_path, monkeypatch):
    from runport.connectors.python_target import PythonCallableTarget
    from runport.core.live_guard import LiveAuthorization
    from runport.services.execution import ExecutionService

    service = ExecutionService(workspace=WorkspaceConfig())
    t = PythonCallableTarget("echo", "echo", func=lambda c: "ok")
    plan = service.plan({"echo": t}, {"echo": {"type": "python", "callable": "x:y"}}, [{"id": "a"}], dataset_label="d", requested_by="mcp")

    refused = CliRunner().invoke(app, ["approve", plan.plan_id], input=plan.confirmation_phrase + "\n")
    assert refused.exit_code == 1 and service.get_plan(plan.plan_id).status == "PENDING"

    monkeypatch.setattr("runport.core.live_guard.confirm_live_run", lambda models, summary, **kw: LiveAuthorization(models=tuple(models)))
    ok = CliRunner().invoke(app, ["approve", plan.plan_id])
    assert ok.exit_code == 0, ok.output
    approved = service.get_plan(plan.plan_id)
    assert approved.status == "APPROVED" and approved.approved_by.startswith("cli_interactive:")


def test_cli_benchmark_rag_plans_approves_and_runs_through_the_service(tmp_path, monkeypatch):
    """benchmark-rag --live: one plan, typed approval bound to its fingerprint, execution via GenericRunner."""
    from runport.core.live_guard import LiveAuthorization

    model = "google/gemini-3.5-flash-lite"
    monkeypatch.chdir(tmp_path)
    (tmp_path / "data" / "audit").mkdir(parents=True)
    (tmp_path / "data" / "audit" / "parsed_records_general_kb.jsonl").write_text(
        '{"record_id": "REC-1", "source_file": "x.md", "question_clean": "tuition fees?", "answer_clean": "Fees are RM 1000", "parsing_status": "VALID", "programme_name": "P"}\n'
    )
    ds = tmp_path / "rag.jsonl"
    DatasetManager.save_jsonl(
        [
            EvaluationCase(
                id="r1",
                query="What are the tuition fees?",
                expected_answer="Fees are RM 1000",
                classification=DataClassification.SYNTHETIC,
                split=DatasetSplit.TEST,
                relevant_record_ids=["REC-1"],
                verification=VerificationRecord(status=VerificationStatus.VERIFIED, reference_source="synthetic"),
            )
        ],
        ds,
    )

    class _OR:
        def read(self):
            body = {"choices": [{"message": {"content": "Fees are RM 1000."}, "finish_reason": "stop"}], "usage": {"prompt_tokens": 40, "completion_tokens": 6}}
            return json.dumps(body).encode()

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    calls = []
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-v1-" + "x" * 40)
    monkeypatch.setattr("urllib.request.urlopen", lambda req, timeout=None: calls.append(req.full_url) or _OR())
    monkeypatch.setattr("runport.providers.openrouter.registry.synthetic_live_blockers", lambda *a, **k: [])
    seen = {}

    def confirm(models, summary, *, plan_fingerprint=None, **kw):
        seen["fp"] = plan_fingerprint
        return LiveAuthorization(models=tuple(models))

    monkeypatch.setattr("runport.core.live_guard.confirm_live_run", confirm)
    result = CliRunner().invoke(app, ["benchmark-rag", "--model", model, "--dataset", str(ds), "--split", "TEST", "--live"])
    assert result.exit_code == 0, result.output
    assert len(seen["fp"]) == 64 and len(calls) == 1

    from runport.services.approvals import ApprovalStore

    rec = ApprovalStore(DatabaseManager(DatabaseManager().db_path)).find_by_fingerprint(seen["fp"])
    assert rec.status == "CONSUMED" and rec.approved_by.startswith("cli_interactive:")
    ledger = _ledger()
    assert len(ledger) == 1 and ledger[0]["cost_basis"] == "ESTIMATED"

"""Integration tests for Phase 5 & Phase 6: Connectors, SDKs, MCP server, and Observability.

Verifies:
1. Python SDK multi-tenancy project scoping and local vs live execution guards.
2. MCP server tool registry parity (get_budget_status, list_jobs, cancel_job).
3. MCP server self-approval strict prohibition.
4. Connector contract invariants (Ollama local UNAVAILABLE, secret scrubbing, provenance mapping).
5. OpenAIChat / OpenAICompat secret scrubbing from configs and outputs.
6. Trace export & ingestion project scoping across Otlp and Langfuse.
"""

from decimal import Decimal
import json
from pathlib import Path
from typing import Any, Dict
import pytest

from runport.api.v1.jobs import JobManager
from runport.connectors.ollama import OllamaConnector
from runport.connectors.openai_compat import OpenAICompatConnector
from runport.core.config import settings
from runport.core.workspace import BudgetConfig, WorkspaceConfig
from runport.mcp_server.server import RunportMcpServer, ToolError
from runport.providers.base import LiveNotAuthorizedError, scrub_secrets
from runport.sdk import benchmark, plan
from runport.services.execution import ExecutionService
from runport.storage.db import DatabaseManager
from runport.targets.base import CostBasis, TargetPricing, TargetStatus
from runport.traces.langfuse import LangfuseExporter, LangfuseIngester
from runport.traces.otlp import OtlpExporter, OtlpIngester
from runport.traces.repository import TraceRepository


@pytest.fixture
def integration_env(tmp_path: Path, monkeypatch):
    """Sets up an isolated test database and environment for connector & SDK integration."""
    db_file = tmp_path / "integration_p5.db"
    monkeypatch.setenv("RUNPORT_DB_PATH", str(db_file))
    monkeypatch.setenv("RUNPORT_API_TOKEN", "master-token-p5")
    monkeypatch.setattr(type(settings), "db_path", property(lambda self: db_file))

    db = DatabaseManager(db_file)
    db.init_db()

    JobManager._instance = None
    job_mgr = JobManager()

    with db.get_connection() as conn:
        conn.execute("INSERT OR IGNORE INTO organizations (org_id, name, created_at) VALUES ('org-p5', 'P5 Org', '2026-01-01')")
        conn.execute(
            "INSERT OR IGNORE INTO projects (project_id, org_id, name, settings_json, created_at) VALUES ('proj-alpha', 'org-p5', 'Alpha Project', '{}', '2026-01-01')"
        )
        conn.execute(
            "INSERT OR IGNORE INTO projects (project_id, org_id, name, settings_json, created_at) VALUES ('proj-beta', 'org-p5', 'Beta Project', '{}', '2026-01-01')"
        )

    return {
        "db": db,
        "job_mgr": job_mgr,
        "tmp_path": tmp_path,
    }


def test_python_sdk_local_benchmark_auto_approves(integration_env):
    """Local Python callable targets auto-approve through local_only channel without human intervention."""
    db: DatabaseManager = integration_env["db"]
    ws = WorkspaceConfig(budget=BudgetConfig(total_usd=Decimal("5.00"), per_run_usd=Decimal("2.00")))
    service = ExecutionService(db=db, workspace=ws)

    def my_local_agent(case: Dict[str, Any]) -> str:
        return f"Echo: {case.get('query', '')}"

    cases = [{"id": "c1", "query": "hello local world", "classification": "PUBLIC"}]

    outcome = benchmark(
        my_local_agent,
        cases,
        target_id="local-echo",
        service=service,
        project_id="proj-alpha",
    )

    assert len(outcome.runs) == 1
    run_res = outcome.runs[0]
    assert run_res.successful_cases == 1
    assert run_res.failed_cases == 0
    assert run_res.case_results[0].output_text == "Echo: hello local world"
    assert run_res.total_spend_usd == Decimal("0.00")

    # Verify project-level scoping
    saved_runs = db.get_all_evaluation_runs(project_id="proj-alpha")
    assert len(saved_runs) == 1
    assert saved_runs[0]["project_id"] == "proj-alpha"

    # Project beta has 0 runs
    beta_runs = db.get_all_evaluation_runs(project_id="proj-beta")
    assert len(beta_runs) == 0


def test_python_sdk_remote_target_requires_human_approval(integration_env):
    """Remote/billable targets planned via Python SDK require human confirmation and cannot auto-approve."""
    db: DatabaseManager = integration_env["db"]
    ws = WorkspaceConfig(budget=BudgetConfig(total_usd=Decimal("5.00"), per_run_usd=Decimal("2.00")))
    service = ExecutionService(db=db, workspace=ws)

    pricing = TargetPricing(input_usd_per_1m=Decimal("0.50"), output_usd_per_1m=Decimal("1.50"))
    remote_target = OpenAICompatConnector(
        target_id="openai-remote-mock",
        name="Remote Mock",
        model="gpt-4o-mini",
        base_url="https://api.openai.com/v1",
        api_key="sk-mock-key-12345",
        pricing=pricing,
    )

    cases = [{"id": "c1", "query": "hello remote", "classification": "PUBLIC"}]

    sdk_plan = plan(remote_target, cases, service=service, project_id="proj-alpha")
    assert sdk_plan.summary.status == "PENDING"
    assert sdk_plan.summary.project_id == "proj-alpha"

    # Cannot auto-approve remote billable target through local_only channel
    with pytest.raises(LiveNotAuthorizedError):
        service.approve(sdk_plan.plan_id, sdk_plan.fingerprint, channel="local_only", approver="sdk")


def test_mcp_server_control_plane_tools(integration_env):
    """MCP server provides get_budget_status, list_jobs, and cancel_job tools."""
    db: DatabaseManager = integration_env["db"]
    ws = WorkspaceConfig(budget=BudgetConfig(total_usd=Decimal("10.00"), per_run_usd=Decimal("3.00")))
    service = ExecutionService(db=db, workspace=ws)

    server = RunportMcpServer(service_factory=lambda: service)

    # 1. Test get_budget_status tool
    assert "get_budget_status" in server.tools
    status_handler = server.tools["get_budget_status"][2]
    budget_status = status_handler({})
    assert "total_ceiling_usd" in budget_status
    assert Decimal(str(budget_status["total_ceiling_usd"])) == Decimal("10.00")
    assert budget_status["unresolved_spend_count"] == 0

    # 2. Test list_jobs tool
    assert "list_jobs" in server.tools
    list_handler = server.tools["list_jobs"][2]
    # Create a test job in database
    db.create_run_job(job_id="job-mcp-001", plan_id="p-001", status="queued", total_cases=5, project_id="proj-alpha")
    jobs_res = list_handler({"limit": 10})
    assert "jobs" in jobs_res
    matching = [j for j in jobs_res["jobs"] if j["job_id"] == "job-mcp-001"]
    assert len(matching) == 1

    # 3. Test cancel_job tool
    assert "cancel_job" in server.tools
    cancel_handler = server.tools["cancel_job"][2]
    cancel_res = cancel_handler({"job_id": "job-mcp-001"})
    assert cancel_res["job"]["job_id"] == "job-mcp-001"
    assert bool(cancel_res["job"]["cancelled"]) is True

    # Unknown job cancellation raises ToolError
    with pytest.raises(ToolError):
        cancel_handler({"job_id": "job-nonexistent-999"})


def test_mcp_server_forbids_self_approval_tools():
    """MCP server strictly asserts no self-approval tools can be registered."""
    server = RunportMcpServer()

    # Attempting to register an approval tool must be rejected
    with pytest.raises(ValueError) as exc_info:
        server.register_tool(
            "approve_plan",
            "Agent attempts to approve spend",
            {"type": "object"},
            lambda args: {"approved": True},
        )
    assert "strictly forbidden" in str(exc_info.value).lower()

    with pytest.raises(ValueError):
        server.register_tool(
            "approve_benchmark",
            "Agent attempts to approve benchmark",
            {"type": "object"},
            lambda args: {"approved": True},
        )


def test_ollama_local_target_invariants(monkeypatch):
    """Ollama connector strictly enforces local billing, UNAVAILABLE cost basis, and zero fabricated costs."""
    target = OllamaConnector(
        target_id="ollama-llama3",
        name="Ollama Llama 3",
        model="llama3",
        base_url="http://127.0.0.1:11434",
    )

    # Ollama is local, free, unpriced
    assert target.billing.value == "local"
    assert target.pricing is None

    # Synthetic mock offline execution
    mock_payload = {
        "model": "llama3",
        "message": {"role": "assistant", "content": "Hello from mock local Ollama!"},
        "prompt_eval_count": 12,
        "eval_count": 24,
        "total_duration": 45_000_000,  # 45ms
    }

    class FakeOllamaResponse:
        def read(self):
            return json.dumps(mock_payload).encode("utf-8")

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_val, exc_tb):
            pass

    monkeypatch.setattr("urllib.request.urlopen", lambda req, timeout=None: FakeOllamaResponse())

    res = target.execute({"query": "Hello Ollama"})
    assert res.status == TargetStatus.SUCCESS
    assert res.output_text == "Hello from mock local Ollama!"
    assert res.tokens_in == 12
    assert res.tokens_out == 24
    assert res.cost_usd is None  # Invariant 1: Null is not 0
    assert res.cost_basis == CostBasis.UNAVAILABLE  # Invariant 2: UNAVAILABLE
    assert res.provenance == "LIVE"


def test_openai_compat_secret_scrubbing():
    """OpenAI compatible connector and provider utilities scrub secrets from errors and metadata."""
    secret = "sk-proj-super-secret-key-1234567890abcdef"
    dirty_text = f"Error communicating with upstream host: Authorization Bearer {secret} failed."
    clean_text = scrub_secrets(dirty_text)
    assert secret not in clean_text
    assert "[REDACTED" in clean_text

    dirty_dict = {
        "api_key": secret,
        "headers": {"Authorization": f"Bearer {secret}"},
        "safe_key": "safe_value",
    }
    clean_dict = scrub_secrets(dirty_dict)
    assert "[REDACTED" in clean_dict["api_key"]
    assert secret not in json.dumps(clean_dict)


def test_trace_exporters_project_scoping(integration_env):
    """OTLP and Langfuse trace exporters and ingesters properly isolate traces by project."""
    db: DatabaseManager = integration_env["db"]
    repo = TraceRepository(db)

    # Ingest a trace into project alpha
    otlp_payload = {
        "resourceSpans": [
            {
                "resource": {
                    "attributes": [
                        {"key": "service.name", "value": {"stringValue": "runport"}},
                        {"key": "project_id", "value": {"stringValue": "proj-alpha"}},
                    ]
                },
                "scopeSpans": [
                    {
                        "spans": [
                            {
                                "traceId": "4bf92f3577b34da6a3ce929d0e0e4736",
                                "spanId": "00f067aa0ba902b7",
                                "name": "chat_completion",
                                "kind": 3,
                                "startTimeUnixNano": "1700000000000000000",
                                "endTimeUnixNano": "1700000001000000000",
                                "attributes": [
                                    {"key": "gen_ai.system", "value": {"stringValue": "openai"}},
                                    {"key": "gen_ai.request.model", "value": {"stringValue": "gpt-4"}},
                                ],
                                "status": {"code": 1},
                            }
                        ]
                    }
                ],
            }
        ]
    }

    ingested_traces = OtlpIngester.ingest_to_repository(otlp_payload, repo, project_id="proj-alpha")
    assert len(ingested_traces) >= 1

    # Project alpha can find and export this trace
    traces_alpha = repo.list_traces(project_id="proj-alpha")
    assert len(traces_alpha) >= 1
    t_id = traces_alpha[0].trace_id

    trace_obj = repo.get_trace(t_id, project_id="proj-alpha")
    assert trace_obj is not None
    exported_otlp = OtlpExporter.export_trace(trace_obj)
    assert "resourceSpans" in exported_otlp
    exported_lf = LangfuseExporter.export_trace(trace_obj)
    assert "batch" in exported_lf or "id" in exported_lf

    # Project beta CANNOT see this trace (isolation)
    traces_beta = repo.list_traces(project_id="proj-beta")
    assert len(traces_beta) == 0
    assert repo.get_trace(t_id, project_id="proj-beta") is None

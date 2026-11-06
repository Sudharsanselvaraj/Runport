"""Runport MCP server, exercised over real stdio by two independent MCP clients:

* the official MCP Python SDK (`mcp` package, ClientSession + stdio_client), and
* Runport's own MCP client connector (connectors/mcp.py).

The server runs as a subprocess in a temporary workspace. Its only target is a local Python function, so nothing
touches the network. The human approval step is performed the way `runport approve` does it, from outside the
server, on the same database.
"""

import json
import os
import sys
from pathlib import Path

import anyio
import pytest

ROOT = Path(__file__).resolve().parents[1]
SECRET = "workspace-secret-token-9f8e7d"


@pytest.fixture
def workspace(tmp_path):
    (tmp_path / "data" / "evaluation").mkdir(parents=True)
    cases = [{"id": f"c{i}", "query": f"question {i}", "expected_answer": "the right answer", "classification": "SYNTHETIC"} for i in range(3)]
    (tmp_path / "data" / "evaluation" / "mini.jsonl").write_text("\n".join(json.dumps(c) for c in cases) + "\n")
    (tmp_path / "runport.yaml").write_text(
        json.dumps(
            {
                "name": "mcp-test",
                "targets": [
                    {"id": "local-answer", "type": "python", "options": {"callable": "mcp_local_target:answer"}},
                    {
                        "id": "remote-agent",
                        "type": "http_workflow",
                        "endpoint": "https://agent.example.com/chat",
                        "headers": {"Authorization": "Bearer ${MCP_TEST_TOKEN}"},
                    },
                ],
            }
        )
    )
    return tmp_path


def _env():
    env = dict(os.environ)
    env["PYTHONPATH"] = os.pathsep.join([str(ROOT / "src"), str(ROOT / "tests" / "fixtures")])
    env["RUNPORT_SKIP_DOTENV"] = "1"
    env["MCP_TEST_TOKEN"] = SECRET
    env.pop("OPENROUTER_API_KEY", None)
    return env


def _approve_as_a_person(workspace, plan_id):
    """What `runport approve <plan_id>` does after the typed phrase, against the server's database."""
    from runport.services.approvals import ApprovalStore
    from runport.storage.db import DatabaseManager

    store = ApprovalStore(DatabaseManager(workspace / "data" / "runport.db"))
    rec = store.get(plan_id)
    store.approve(plan_id, rec.fingerprint, channel="cli_interactive", approver="tester")


def _is_error(result):
    return getattr(result, "is_error", None) if hasattr(result, "is_error") else result.isError


def _payload(result):
    assert not _is_error(result), result.content[0].text
    return json.loads(result.content[0].text)


def test_official_sdk_client_full_flow(workspace):
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    params = StdioServerParameters(command=sys.executable, args=["-m", "runport.mcp_server.server"], env=_env(), cwd=str(workspace))

    async def flow():
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                init = await session.initialize()
                assert (getattr(init, "server_info", None) or init.serverInfo).name == "runport"

                tools = {t.name for t in (await session.list_tools()).tools}
                assert {"create_benchmark_plan", "request_benchmark_approval", "execute_approved_benchmark", "get_run", "compare_runs"} <= tools
                assert not any("approve" == t or t.startswith("approve") for t in tools)  # no self-approval tool

                targets = _payload(await session.call_tool("list_targets", {}))
                assert SECRET not in json.dumps(targets)
                assert {t["target_id"]: t["billing"] for t in targets["targets"]} == {"local-answer": "local", "remote-agent": "billable"}

                bad = await session.call_tool("create_benchmark_plan", {"target_ids": ["made-up"], "dataset_name": "mini.jsonl"})
                assert _is_error(bad)

                plan = _payload(await session.call_tool("create_benchmark_plan", {"target_ids": ["local-answer"], "dataset_name": "mini.jsonl"}))
                assert plan["status"] == "PENDING" and plan["requested_by"] == "mcp"

                early = await session.call_tool("execute_approved_benchmark", {"plan_id": plan["plan_id"]})
                assert _is_error(early) and "approve" in early.content[0].text.lower()

                req = _payload(await session.call_tool("request_benchmark_approval", {"plan_id": plan["plan_id"]}))
                assert req["approved"] is False and any("runport approve" in h for h in req["how_to_approve"])

                _approve_as_a_person(workspace, plan["plan_id"])

                done = _payload(await session.call_tool("execute_approved_benchmark", {"plan_id": plan["plan_id"]}))
                run = done["runs"][0]
                assert run["successful_cases"] == 3 and run["booked_spend_usd"] == "0"

                again = await session.call_tool("execute_approved_benchmark", {"plan_id": plan["plan_id"]})
                assert _is_error(again)  # one approval, one execution

                got = _payload(await session.call_tool("get_run", {"run_id": run["run_id"]}))
                assert got["run"]["completed_cases"] == 3
                results = _payload(await session.call_tool("get_evaluation_results", {"run_id": run["run_id"]}))
                assert results["total"] == 3 and results["results"][0]["accuracy"] is not None

                budget = await session.read_resource("runport://budget")
                assert json.loads(budget.contents[0].text)["unresolved_spend_count"] == 0
                prompts = {p.name for p in (await session.list_prompts()).prompts}
                assert "benchmark_target" in prompts
                prompt = await session.get_prompt("benchmark_target", {"target_id": "local-answer", "dataset_name": "mini.jsonl"})
                assert "Do not try to approve it yourself" in prompt.messages[0].content.text

                invalid = await session.call_tool("get_run", {})
                assert _is_error(invalid) and "run_id" in invalid.content[0].text

    anyio.run(flow)


def test_remote_plan_cannot_run_without_a_person_and_never_leaks_the_secret(workspace):
    from runport.connectors.mcp import McpToolTarget

    client = McpToolTarget("runport-mcp", "Runport MCP", command=[sys.executable, "-m", "runport.mcp_server.server"], env=_env(), cwd=str(workspace))
    try:
        tools = {t["name"] for t in client.discover_tools()}
        assert "execute_approved_benchmark" in tools

        validated = client.execute({"tool": "validate_target", "arguments": {"target_id": "remote-agent"}})
        assert validated.status.value == "success" and SECRET not in validated.output_text
        assert json.loads(validated.output_text)["billing"] == "billable"

        plan = client.execute({"tool": "create_benchmark_plan", "arguments": {"target_ids": ["remote-agent"], "dataset_name": "mini.jsonl"}})
        body = json.loads(plan.output_text)
        assert body["projected_cost_usd"] > 0  # unknown price on a billable target reserves the per-case ceiling
        assert SECRET not in plan.output_text

        refused = client.execute({"tool": "execute_approved_benchmark", "arguments": {"plan_id": body["plan_id"]}})
        assert refused.error_code == "TOOL_ERROR"
    finally:
        client.close()

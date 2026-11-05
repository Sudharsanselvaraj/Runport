---
title: MCP
description: Benchmark an MCP server's tools, and let coding agents drive Runport through its own MCP server.
---

> [!WARNING]
> Experimental. The MCP connector covers tools only and stays experimental until it has been exercised against more real servers.

`McpToolTarget` connects to an MCP server, discovers its tools and calls one tool per benchmark case. It speaks JSON-RPC 2.0 MCP directly, so it needs no extra dependency.

## Create a target

```python
from runport.connectors.mcp import McpToolTarget

# stdio: Runport launches the server as a child process
target = McpToolTarget(
    target_id="docs-mcp",
    name="Docs MCP server",
    command=["python", "-m", "my_mcp_server"],
    timeout_seconds=20.0,
)

# Streamable HTTP
target = McpToolTarget(
    target_id="search-mcp",
    name="Search MCP",
    url="https://mcp.example.com/mcp",
    headers={"Authorization": "Bearer <token>"},
    tool_name="search",
    arguments_template={"query": "{{query}}"},
)

print([t["name"] for t in target.discover_tools()])
result = target.execute({"tool": "search", "arguments": {"query": "runport"}})
target.close()
```

| Parameter | Default | Meaning |
|---|---|---|
| `command` | — | Server command as an argument list (stdio). Give this or `url` |
| `env`, `cwd` | `None` | Environment and working directory for the stdio process |
| `url` | — | Streamable HTTP endpoint. Give this or `command` |
| `headers` | `None` | HTTP headers, for example a bearer token |
| `tool_name` | `None` | Default tool when a case names none |
| `arguments_template` | `None` | Arguments with `{{field}}` placeholders filled from the case |
| `validate_arguments` | `enforce` | `enforce`, `record` or `off` (see below) |
| `timeout_seconds` | `30.0` | Deadline for each request |
| `init_timeout_seconds` | `timeout_seconds` | Deadline for `initialize` |
| `allow_private`, `allow_localhost`, `host_allowlist` | off | Network safety controls for `url` |

## Cases

A case picks its tool with `tool` and passes `arguments`. Without them the target's `tool_name` is used and the arguments come from `arguments_template`, or from the case's other fields.

```json
{"tool": "search", "arguments": {"query": "budget caps"}}
```

## What is recorded

- `latency_ms` is the `tools/call` round trip only. Starting the session (launching the process, `initialize`, `tools/list`) is reported once as `metadata.session_setup_ms` on the case that opened it. Later cases reuse the session.
- `metadata.schema_validation` holds the result of checking the arguments against the tool's `inputSchema`. With `enforce` an invalid case fails with `SCHEMA_INVALID_ARGUMENTS` and the tool is not called. With `record` it is called anyway. Schema keywords the validator does not implement are listed in `unsupported_rules`, never counted as passed.
- Tool errors (`isError: true`) fail with `TOOL_ERROR`, JSON-RPC errors with `JSONRPC_<code>`, protocol violations with `PROTOCOL_ERROR`, and deadlines with `TIMEOUT`. After a timeout the client sends `notifications/cancelled` and closes the session, and the next case opens a new one.
- MCP reports no price or tokens, so cost and tokens stay empty. A stdio server is a local process and is booked `UNAVAILABLE`. A Streamable HTTP server on a non-loopback host may bill, so each call is booked `UNRESOLVED` (and the run halts until reconciled) unless you declare the target free with `billing="unbilled"`.

## Safety

Tool calls are never retried, because tools can have side effects. `url` is checked by the same network safety rules as the [HTTP connector](/custom-http#network-safety). Header values, and `env` values whose variable name looks like a credential (`*KEY*`, `*TOKEN*`, `*SECRET*` and so on), are never stored on results and are redacted from errors, server stderr, tool output and metadata.

Resources, prompts, sampling, OAuth discovery and the older HTTP+SSE transport are not supported yet.

## Runport as an MCP server

`runport mcp serve` exposes Runport to coding agents (Claude Code, Cursor, VS Code or your own agent) over stdio.

```json
{"mcpServers": {"runport": {"command": "uv", "args": ["run", "runport", "mcp", "serve"], "cwd": "/path/to/your/project"}}}
```

| Tool | What it does |
|---|---|
| `list_connectors` | The connector capability matrix |
| `list_models` | Catalog models and their prices |
| `list_targets` | Targets declared in `runport.yaml` (type, billing mode, header names only) |
| `list_datasets` | Datasets in `data/evaluation` with case counts |
| `validate_target` | Builds a target without sending anything |
| `create_benchmark_plan` | A fingerprinted plan with worst-case spend and blockers. Sends nothing |
| `request_benchmark_approval` | Tells the agent how a person approves the plan. Approves nothing |
| `get_plan_status` | `PENDING`, `APPROVED` (and by whom) or `CONSUMED` |
| `execute_approved_benchmark` | Runs a plan a person approved, once, through the guarded runner |
| `get_run`, `get_evaluation_results`, `compare_runs` | Read results; unmeasured metrics stay `null` |

Resources: `runport://connectors`, `runport://models`, `runport://targets`, `runport://datasets`, `runport://runs`,
`runport://runs/{run_id}` and `runport://budget`. Prompts: `benchmark_target`, `investigate_failed_cases`, `compare_candidates`.

### What an agent cannot do

- **Approve spend.** There is no approve tool, and the approval store rejects every channel the server could use. A person approves
  with `runport approve <plan_id>` (typed phrase in a terminal) or in the Web UI. Approvals expire after 15 minutes and are used once.
- **Bypass the runner.** Execution re-derives the plan fingerprint from the current workspace and dataset, consumes the approval
  atomically, and runs `GenericRunner`: privacy gate, budget preflight, persistence and spend booking all apply.
- **Choose arbitrary endpoints or commands.** Targets are those declared in `runport.yaml` and catalog models only.
- **Read secrets.** Listings show header names, never values, and every result is scrubbed.

The server is tested over real stdio with the official MCP Python SDK client and with Runport's own MCP client
(`tests/test_mcp_server.py`). It speaks protocol versions `2025-06-18`, `2025-03-26` and `2024-11-05`; Streamable HTTP serving,
sampling and resource subscriptions are not implemented.

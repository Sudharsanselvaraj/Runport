---
title: MCP servers
description: Benchmark the tools of a Model Context Protocol server over stdio or Streamable HTTP (experimental).
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
- Cost is `UNAVAILABLE`: MCP reports no price or tokens, so cost and tokens stay empty rather than `$0.00`.

## Safety

Tool calls are never retried, because tools can have side effects. `url` is checked by the same network safety rules as the [HTTP connector](/custom-http#network-safety). Header and `env` values are never stored on results and are redacted from errors, server stderr, tool output and metadata.

Resources, prompts, sampling, OAuth discovery and the older HTTP+SSE transport are not supported yet.

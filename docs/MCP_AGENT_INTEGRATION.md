# Model Context Protocol (MCP) Agent Integration Guide

Runport exposes a production-grade Model Context Protocol (MCP) server supporting both **stdio** (JSON-RPC over standard I/O) and **streamable HTTP** (Server-Sent Events) transports.

This allows autonomous coding agents and IDEs—including Claude Desktop, Cursor, VS Code (Cline / Roo Code), and Windsurf—to plan, inspect, and benchmark AI systems with zero code required.

---

## 1. Safety Invariants & Agent Permissions

Runport adheres to strict security invariants by construction:

1. **Agents Cannot Approve Live Spend**:
   There is **no** `approve_plan` tool registered on the server. The approval ledger strictly rejects any automated attempt to approve spend. Live execution requires explicit human authorization via `runport approve <plan_id>` in the CLI or through the Web UI.
2. **Deterministic Plan Consumption**:
   Approvals are bound to the cryptographic SHA-256 fingerprint of the candidate models, prompt templates, and budget caps. An approved plan runs exactly once.
3. **Secret Scrubbing**:
   Target listings expose only header names (never bearer tokens or secret values). Request events and traces are sanitized automatically.

---

## 2. Supported Transports & Protocols

Runport implements the MCP specification supporting protocol versions up to **`2026-07-28`**:

- **Stdio Transport**: Command-line subprocess communication for local IDEs (default).
- **Streamable HTTP (SSE) Transport**: Hosted or Dockerized daemon exposing `/mcp/sse` and `/mcp/messages`.

---

## 3. IDE Configuration Blueprints

### A. Claude Desktop

Edit your Claude Desktop configuration file:
- **macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`
- **Windows**: `%APPDATA%\Claude\claude_desktop_config.json`
- **Linux**: `~/.config/Claude/claude_desktop_config.json`

#### Local Stdio Setup
```json
{
  "mcpServers": {
    "runport": {
      "command": "runport",
      "args": ["mcp"]
    }
  }
}
```

#### Remote Streamable HTTP (SSE) Setup
```json
{
  "mcpServers": {
    "runport": {
      "url": "http://127.0.0.1:8000/mcp/sse",
      "headers": {
        "Authorization": "Bearer YOUR_RUNPORT_API_KEY"
      }
    }
  }
}
```

---

### B. Cursor IDE

In Cursor, open **Settings → Features → MCP**, or create `.cursor/mcp.json` in your workspace root:

```json
{
  "mcpServers": {
    "runport": {
      "command": "runport",
      "args": ["mcp"]
    }
  }
}
```

---

### C. VS Code (Cline / Roo Code)

In VS Code with the Cline or Roo Code extension, configure `mcpServers` in your global extension settings:

```json
{
  "mcpServers": {
    "runport": {
      "command": "runport",
      "args": ["mcp"],
      "disabled": false,
      "autoApprove": [
        "list_connectors",
        "list_models",
        "list_targets",
        "list_datasets",
        "validate_target",
        "create_benchmark_plan",
        "request_benchmark_approval",
        "get_plan_status",
        "get_run",
        "get_evaluation_results",
        "compare_runs"
      ]
    }
  }
}
```

---

## 4. Available MCP Tools

| Tool Name | Purpose | Live Spend Permitted? |
|:---|:---|:---:|
| `list_connectors` | Connector capability matrix and test statuses | No |
| `list_models` | Verified catalog models with rate benchmarks | No |
| `list_targets` | Declared workspace targets in `runport.yaml` | No |
| `list_datasets` | Local evaluation datasets in `data/evaluation/` | No |
| `validate_target` | Probe a model or target spec without live requests | No |
| `create_benchmark_plan` | Calculate worst-case spend, blockers, and SHA-256 fingerprint | No |
| `request_benchmark_approval` | Retrieve instructions for human approval | No |
| `get_plan_status` | Check if a plan is PENDING, APPROVED, or CONSUMED | No |
| `execute_approved_benchmark` | Execute an approved benchmark through `GenericRunner` | Yes (guarded) |
| `get_run` | Retrieve run status, completed cases, and costs | No |
| `get_evaluation_results` | Inspect per-case outputs, latency, and scores | No |
| `compare_runs` | Compare metrics between two evaluation runs | No |

---

## 5. Typical Agent Workflow

```
       [Agent Prompt]
             │
             ▼
      list_targets()
             │
             ▼
  create_benchmark_plan()  ───────►  Returns Plan ID & Fingerprint
             │                        Status: PENDING ($0.00 spent)
             ▼
request_benchmark_approval() ─────►  Agent prompts human:
             │                       "Please run: runport approve plan-abc123"
             ▼
      [Human Approves]      ───────►  Operator authorizes in terminal/web UI
             │
             ▼
execute_approved_benchmark() ────►  Guarded execution consumes approval
             │                        Runs benchmark within fail-closed cap
             ▼
   get_evaluation_results() ─────►  Agent analyzes accuracy, latency, spend
```

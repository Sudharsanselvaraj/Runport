# MCP Architecture

Runport uses MCP in two directions. Both are implemented for local use and tested; remote (HTTP) serving and MCP-native
authentication are not.

---

## 1. Runport as an MCP client (benchmarking MCP servers)

**Code:** `src/runport/connectors/mcp.py` (`McpToolTarget`). Dependency-free JSON-RPC 2.0.

| Area | Implemented | Not implemented |
|:---|:---|:---|
| Transports | stdio (child process), Streamable HTTP (JSON and SSE replies, `Mcp-Session-Id`, DELETE on close) | Legacy HTTP+SSE |
| Lifecycle | `initialize`, version negotiation (`2025-06-18`, `2025-03-26`, `2024-11-05`), `notifications/initialized`, ping replies, close | `2025-11-25`, `2026-07-28` (`server/discover`) |
| Tools | Paginated `tools/list`, `tools/call`, `inputSchema` validation (`enforce` / `record` / `off`, unsupported keywords reported), `structuredContent` | Output schema validation |
| Other primitives | — | `resources/*`, `prompts/*`, sampling, elicitation, OAuth |
| Errors | `TOOL_ERROR`, `JSONRPC_<code>`, `PROTOCOL_ERROR`, `TIMEOUT` with `notifications/cancelled` and session teardown | — |
| Cost | stdio = local (`UNAVAILABLE`); non-loopback HTTP = billable (`UNRESOLVED` + halt unless declared `unbilled`) | Tool pricing |
| Secrets | Header values and credential-named env values redacted from all output | — |

**Tests:** `tests/test_mcp_connector.py` (fixture server with echo, add, fail, hang, leak tools; scripted HTTP fake).

**Scope note:** calling a server's tools benchmarks the tool layer, not an agent's decisions. Agent evaluation needs the agent as
the target with its tool calls captured as `tool` spans (`docs/CANONICAL_TRACE_SCHEMA.md`).

---

## 2. Runport as an MCP server (agents operating Runport)

**Code:** `src/runport/mcp_server/server.py` (`RunportMcpServer`), started with `runport mcp serve` (stdio).

```text
agent ── stdio JSON-RPC ──► RunportMcpServer ──► ExecutionService ──► GenericRunner
                                   │                     │
                                   │                     └─ ApprovalStore (no channel available to MCP)
                                   └─ reads: registry, catalog, workspace targets, datasets, runs, budget
```

| Tools | Effect |
|:---|:---|
| `list_connectors`, `list_models`, `list_targets`, `list_datasets` | Read only. Targets show type, billing, header **names** |
| `validate_target` | Builds a target, sends nothing |
| `create_benchmark_plan` | Stores a `PENDING` plan (requested_by `mcp`) with worst-case spend and blockers |
| `request_benchmark_approval`, `get_plan_status` | Tells the agent how a person approves; approves nothing |
| `execute_approved_benchmark` | Runs a plan a person approved, once |
| `get_run`, `get_evaluation_results`, `compare_runs` | Read results; nulls stay null |

Resources: `runport://connectors`, `models`, `targets`, `datasets`, `runs`, `budget`, template `runport://runs/{run_id}`.
Prompts: `benchmark_target`, `investigate_failed_cases`, `compare_candidates`.

**Security properties (each has a test):**
1. No approve tool; `ApprovalStore.approve` rejects non-human channels (`tests/test_integrity_security.py`).
2. Plans run at most once; fingerprint re-derived from the current workspace and dataset (`tests/test_mcp_server.py`).
3. Targets restricted to `runport.yaml` and the catalog; agents cannot point Runport at new URLs or commands.
4. Secret values never returned (asserted with a real env secret in `tests/test_mcp_server.py`).
5. Invalid tool arguments return `isError` results; unknown tools return JSON-RPC `-32602`.

**Tests:** `tests/test_mcp_server.py` drives the server over real stdio with the official MCP Python SDK (`mcp` 2.3.0, dev-only
dependency) and with Runport's own client, covering plan → refused execution → human approval → execution → reuse refused.

---

## 3. Gaps and design for remote use

| Gap | Design |
|:---|:---|
| No Streamable HTTP server | Mount the same `RunportMcpServer.handle` behind `/mcp` in the FastAPI app (no second implementation). |
| No auth for remote MCP | Bearer API keys with scopes (`docs/SDK_API_CONTRACT.md`); tool list filtered by scope; `plans:approve` never granted to agent keys by default. |
| A local agent with shell access can still run `runport approve` or call `/api/runs/approve` | Documented operating rule: do not give agents a terminal that can type the phrase, or the API token. Hosted mode removes the shared-token path. |
| Runs block the stdio loop | After async jobs (F2): `execute_approved_benchmark` returns a run id; add `get_run_status` and an events resource. |
| Protocol versions | Add `2025-11-25` after reviewing its changes; track the SDK's supported list in a test. |
| MCP calls not traced | Emit `tool` spans from the client; record server tool invocations in the audit log. |

**Acceptance for "complete MCP ecosystem":** an external agent connects over HTTP with a scoped key, discovers Runport, creates a
plan, a person approves it in the UI, the agent executes it and reads results and traces; every step is in the audit log; the same
flow over stdio still passes; refusal tests for approval, scope and fingerprint changes pass for both transports.

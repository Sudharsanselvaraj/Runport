# Runport Connector Catalog & Status

Runport provides a decoupled connector ecosystem enabling honest, cost-controlled benchmarking across raw LLM completion endpoints, prompt wrappers, and multi-step workflow pipelines.

---

## 1. Connector Status Matrix

| Connector Type | Protocol / Target | Status | Capabilities | Cost Accounting |
|:---|:---|:---:|:---|:---:|
| `openai_compat` | OpenAI Chat Completions API | **Stable** | `streaming`, `logprobs`, `structured_output`, `usage` | `ESTIMATED` (via catalog rates) |
| `openrouter` | OpenRouter Router & Meta-API | **Stable** | `streaming`, `logprobs`, `structured_output`, `usage`, `cost` | `ACTUAL` (provider reported) |
| `dify` | Dify Chat & Workflow Apps | **Stable** | `streaming`, `usage`, `per_step_trace` (workflows) | `ESTIMATED` / `UNAVAILABLE` |
| `http_workflow` | Custom REST / Webhook Endpoints | **Stable** | `text`, `json` | `ESTIMATED` / `UNAVAILABLE` |
| `python_target` | In-Process Python Callables & CLI Binaries | **Stable** | `structured_output` | `UNAVAILABLE` ($0.00 compute) |
| `ollama` | Local Ollama Engine (`/api/chat`, `/api/generate`) | **Stable** | `streaming`, `structured_output`, `usage` | `ACTUAL-LOCAL` ($0.00 compute) |
| `flowise` | Flowise AI Flow Runner | *Experimental* | `streaming` | `UNAVAILABLE` |
| `langflow` | Langflow Flow Execution Engine | *Experimental* | `streaming` | `UNAVAILABLE` |
| `n8n` | n8n Webhook Workflow Automation | *Experimental* | `text`, `json` | `UNAVAILABLE` |
| `langgraph` | LangGraph StateGraph HTTP Endpoints | *Experimental* | `streaming`, `per_step_trace` | `UNAVAILABLE` |
| `mcp` | Model Context Protocol servers (stdio, Streamable HTTP) | *Experimental* | `tools`, `json`, `schema_validation` | `UNAVAILABLE` |

> [!NOTE]
> Connectors marked **Experimental** (`flowise`, `langflow`, `n8n`, `langgraph`, `mcp`) are community reference adapters and will remain labeled experimental until they complete the formal offline contract test suite.

---

## 2. Invariants & Security Controls

1. **SSRF Safeguards**: All HTTP-based connectors (`http_workflow`, `openai_compat`, `dify`, `ollama`) strictly validate target endpoints against SSRF risks. Requests to cloud metadata services (`169.254.169.254`) and internal RFC 1918 subnets are blocked fail-closed by default.
2. **Secret Scrubbing**: API keys, Bearer tokens, and sensitive headers are scrubbed before persistence, trace emission, or report export.
3. **Null is Not 0**: Missing token counts or latency metrics remain `None` / `UNAVAILABLE`.

---

## 3. MCP Tool Connector (Experimental)

`McpToolTarget` (`src/runport/connectors/mcp.py`) benchmarks the tools of an existing MCP server. It implements a small JSON-RPC 2.0 MCP client itself (no new runtime dependency): `initialize` with protocol-version negotiation (`2025-06-18`, `2025-03-26`, `2024-11-05`), `notifications/initialized`, paginated `tools/list`, `tools/call`, and session close.

```python
from runport.connectors.mcp import McpToolTarget

# stdio: Runport launches the server process
target = McpToolTarget("docs-mcp", "Docs MCP server", command=["python", "-m", "my_mcp_server"], timeout_seconds=20)

# Streamable HTTP: one endpoint, JSON or SSE replies, Mcp-Session-Id handled automatically
target = McpToolTarget(
    "search-mcp",
    "Search MCP",
    url="https://mcp.example.com/mcp",
    headers={"Authorization": "Bearer ..."},
    tool_name="search",
    arguments_template={"query": "{{query}}"},
)

result = target.execute({"tool": "search", "arguments": {"query": "runport"}})
target.close()
```

- **Case shape**: `{"tool": ..., "arguments": {...}}`; without them the target's `tool_name` and `arguments_template` (rendered with `{{field}}` placeholders) are used.
- **Latency**: `latency_ms` and `metadata.tool_latency_ms` measure only the `tools/call` round trip. Session start-up (process launch, `initialize`, `tools/list`) is recorded separately as `metadata.session_setup_ms` on the case that opened the session.
- **Argument validation**: arguments are validated against the tool's discovered `inputSchema` (`validate_arguments="enforce"` by default; `"record"` validates but still calls; `"off"` skips). Schema keywords outside the supported subset are listed in `metadata.schema_validation.unsupported_rules` rather than treated as passed.
- **Errors**: tool errors (`isError: true`) → `FAILED` / `TOOL_ERROR`; JSON-RPC errors → `JSONRPC_<code>`; malformed messages, unsupported protocol versions or a dead process → `PROTOCOL_ERROR`; deadlines → `TIMEOUT` (a `notifications/cancelled` is sent and the session is torn down, so the next case starts fresh).
- **Cost**: MCP tool calls carry no price or token usage, so `cost_usd` and tokens stay `None` with provenance `UNAVAILABLE` — never `$0.00`.
- **Safety**: tool calls are never retried (tools may have side effects). HTTP URLs pass the SSRF check. Header and `env` values are redacted from errors, server stderr tails, tool output and metadata; they are never stored on results. The connector is only the transport step of the runner guard order.
- **Not yet supported**: resources, prompts, sampling, OAuth discovery and the legacy HTTP+SSE transport.

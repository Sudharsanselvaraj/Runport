# Runport Connector Catalog & Status

Runport provides a decoupled connector ecosystem enabling honest, cost-controlled benchmarking across raw LLM completion endpoints, prompt wrappers, and multi-step workflow pipelines.

---

## 1. Connector Capability Matrix

<!-- BEGIN CONNECTOR MATRIX (generated from src/runport/connectors/registry.py; do not edit by hand) -->
| Connector | Name | Status | Integration | Tested | Streaming | Tool calls | Structured output | Per-step trace | Usage | Cost | Errors / timeouts |
|:---|:---|:---:|:---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| `openai_compat` | OpenAI / OpenAI-compatible | **Stable** | native | yes | — | — | partial | — | yes | partial | yes |
| `openrouter` | OpenRouter | **Stable** | native | yes | — | — | — | — | yes | yes | yes |
| `dify` | Dify | **Stable** | native | yes | yes | — | — | partial | yes | partial | yes |
| `http_workflow` | Generic HTTP endpoint | **Stable** | generic http | yes | — | — | — | — | partial | partial | yes |
| `python_target` | Python callable | **Stable** | in process | yes | — | — | partial | — | — | — | yes |
| `subprocess` | Subprocess (stdin/stdout) | **Stable** | in process | yes | — | — | — | — | — | — | yes |
| `ollama` | Ollama | **Stable** | native | yes | — | — | partial | — | yes | — | yes |
| `mcp` | MCP server (tools) | *Experimental* | native | yes | — | yes | yes | — | — | — | yes |
| `flowise` | Flowise | *Experimental* | generic http | partial | — | — | — | — | — | — | yes |
| `langflow` | Langflow | *Experimental* | generic http | partial | — | — | — | — | — | — | yes |
| `n8n` | n8n | *Experimental* | generic http | partial | — | — | — | — | — | — | yes |
| `langgraph` | LangGraph | *Experimental* | generic http | partial | — | — | — | — | — | — | yes |
| `vllm` | vLLM | Via | via `openai_compat` | — | — | — | — | — | yes | partial | yes |
| `lm_studio` | LM Studio | Via | via `openai_compat` | — | — | — | — | — | yes | partial | yes |
| `localai` | LocalAI | Via | via `openai_compat` | — | — | — | — | — | yes | partial | yes |
| `litellm` | LiteLLM proxy | Via | via `openai_compat` | — | — | — | — | — | yes | partial | yes |
| `groq` | Groq | Via | via `openai_compat` | — | — | — | — | — | yes | partial | yes |
| `together` | Together | Via | via `openai_compat` | — | — | — | — | — | yes | partial | yes |
| `fireworks` | Fireworks | Via | via `openai_compat` | — | — | — | — | — | yes | partial | yes |
| `deepinfra` | DeepInfra | Via | via `openai_compat` | — | — | — | — | — | yes | partial | yes |
| `deepseek` | DeepSeek | Via | via `openai_compat` | — | — | — | — | — | yes | partial | yes |
| `mistral` | Mistral | Via | via `openai_compat` | — | — | — | — | — | yes | partial | yes |
| `anthropic` | Anthropic | Via | via `openrouter` | — | — | — | — | — | yes | yes | yes |
| `gemini` | Gemini | Via | via `openrouter` | — | — | — | — | — | yes | yes | yes |
| `langchain` | LangChain | Planned | none | — | — | — | — | — | — | — | — |
| `crewai` | CrewAI | Planned | none | — | — | — | — | — | — | — | — |
| `llamaindex` | LlamaIndex | Planned | none | — | — | — | — | — | — | — | — |
<!-- END CONNECTOR MATRIX -->

Legend: **yes** implemented and covered by offline tests, **partial** implemented with limits (see notes), **—** not implemented.
**Stable** and *Experimental* rows have their own module. **Via** rows have no adapter of their own: they are reached through the connector named
in the Integration column and have exactly that connector's capabilities. **Planned** rows are not implemented; benchmark those frameworks
today through `http_workflow` or a Python callable.

Notes:

- `openai_compat`: Chat Completions only; response_format is passed through, not validated. Cost only with configured pricing (ESTIMATED); otherwise UNRESOLVED for remote hosts.
- `openrouter`: ACTUAL when OpenRouter reports USD cost, ESTIMATED from catalog x reported tokens, otherwise UNRESOLVED.
- `dify`: Streaming via SSE. Workflow apps record node steps in metadata (not yet as trajectory spans).
- `http_workflow`: Tokens only if the response has a usage object. Cost only with configured pricing.
- `python_target`: Local execution: cost UNAVAILABLE. Returns dicts as JSON text.
- `subprocess`: Local execution: cost UNAVAILABLE.
- `ollama`: Non-streaming /api/chat. format=json supported. Local hosts book UNAVAILABLE; remote hosts are billable.
- `mcp`: Calls MCP tools directly (stdio, Streamable HTTP); validates arguments against inputSchema; returns structuredContent.
- `flowise`: Thin HTTP wrapper over the prediction endpoint; no streaming.
- `langflow`: Thin HTTP wrapper over the run endpoint; no streaming.
- `n8n`: Webhook POST.
- `langgraph`: POST /runs/wait and read the last message. No streaming and no per-step trace yet.
- `anthropic`: No native Messages API adapter; reach Claude models through OpenRouter.
- `gemini`: No native Gemini adapter; reach Gemini models through OpenRouter.
- `langchain`: No callback integration. Benchmark a LangChain app today via http_workflow or a python callable.
- `crewai`: Use http_workflow or a python callable.
- `llamaindex`: Use http_workflow or a python callable.

The matrix is generated from `CONNECTOR_MATRIX` in `src/runport/connectors/registry.py`; `tests/test_capability_registry.py` fails if this
table, `README.md`, `docs/connectors.md` or the landing page disagree with it.

---

## 2. Invariants & Security Controls

1. **SSRF safeguards**: every URL-based connector validates its endpoint. Cloud metadata (`169.254.169.254`) and private subnets are
   blocked unless explicitly allowed.
2. **Billing mode**: each target is `local` (in-process, subprocess, MCP stdio, or a loopback URL), `billable` (any other URL), or
   `unbilled` (a remote endpoint the operator declares free with `billing: unbilled`). A missing cost from a `billable` target is booked
   `UNRESOLVED` and halts the run until reconciled; it is never booked as `$0.00`. Local and declared-free targets book `UNAVAILABLE`.
3. **Confidentiality**: only `PUBLIC` and `SYNTHETIC` cases are sent to non-local targets. A case without a classification is
   `UNCLASSIFIED` and blocked.
4. **Secret scrubbing**: credentials in `runport.yaml` must be environment references (`$NAME` or `${NAME}`). Header values never
   appear in plans, results, traces or exports.
5. **Null is not 0**: missing token counts, latency and cost stay `None`.

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
- **Cost**: MCP tool calls carry no price or token usage, so `cost_usd` and tokens stay `None`. A stdio server is a local process (`UNAVAILABLE`); a Streamable HTTP server on a non-loopback host is billable, so a call is booked `UNRESOLVED` unless the target is declared `billing: unbilled`.
- **Safety**: tool calls are never retried (tools may have side effects). HTTP URLs pass the SSRF check. Header values, and `env` values whose variable name looks like a credential, are redacted from errors, server stderr tails, tool output and metadata; they are never stored on results. The connector is only the transport step of the runner guard order.
- **Not yet supported**: resources, prompts, sampling, OAuth discovery and the legacy HTTP+SSE transport.

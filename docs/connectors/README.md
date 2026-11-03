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

> [!NOTE]
> Connectors marked **Experimental** (`flowise`, `langflow`, `n8n`, `langgraph`) are community reference adapters and will remain labeled experimental until they complete the formal offline contract test suite.

---

## 2. Invariants & Security Controls

1. **SSRF Safeguards**: All HTTP-based connectors (`http_workflow`, `openai_compat`, `dify`, `ollama`) strictly validate target endpoints against SSRF risks. Requests to cloud metadata services (`169.254.169.254`) and internal RFC 1918 subnets are blocked fail-closed by default.
2. **Secret Scrubbing**: API keys, Bearer tokens, and sensitive headers are scrubbed before persistence, trace emission, or report export.
3. **Null is Not 0**: Missing token counts or latency metrics remain `None` / `UNAVAILABLE`.

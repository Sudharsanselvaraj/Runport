# Connectors & Evaluation Targets

Runport evaluates any AI target — raw LLM endpoints, prompt wrappers, local models, or compound multi-step workflow pipelines — through a unified `Target` protocol.

Every connector receives a standard case payload and returns a normalized [`TargetResult`](../src/runport/targets/base.py), abstracting away transport details, authentication, and parsing logic.

---

## 1. Connector Status Matrix

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

See [docs/connectors/README.md](connectors/README.md) for the legend and per-connector notes.

---

## 2. Direct Model Connectors

### 2.1 OpenRouter (`openrouter`)
Evaluates 200+ models via OpenRouter's unified API with provider-reported billing headers:

```yaml
# runport.yaml
targets:
  - id: "gemini-flash"
    connector: "openrouter"
    model: "google/gemini-2.0-flash-001"
    temperature: 0.0
    max_tokens: 256
```

```bash
export OPENROUTER_API_KEY="sk-or-v1-..."
uv run runport benchmark --model google/gemini-2.0-flash-001 --live
```

### 2.2 OpenAI-Compatible (`openai_compat`)
Works out of the box with OpenAI, vLLM, Together AI, Mistral, Groq, and Anyscale:

```yaml
targets:
  - id: "vllm-llama"
    connector: "openai_compat"
    base_url: "http://127.0.0.1:8000/v1"
    model: "meta-llama/Llama-3.1-8B-Instruct"
    api_key_env: "VLLM_API_KEY"
    pricing:
      input_usd_per_1m: 0.15
      output_usd_per_1m: 0.60
```

### 2.3 Ollama (`ollama`)
Evaluates local open-source models completely offline with zero API cost:

```yaml
targets:
  - id: "ollama-qwen"
    connector: "ollama"
    base_url: "http://127.0.0.1:11434"
    model: "qwen2.5:7b"
    timeout_s: 60.0
```

---

## 3. Workflow & Agent Connectors

### 3.1 Dify Connector (`dify`)
Evaluates Dify Chatbot and Workflow applications via REST or Server-Sent Events (SSE) streaming:

```yaml
targets:
  - id: "support-triage-flow"
    connector: "dify"
    endpoint: "https://api.dify.ai/v1/workflows/run"
    app_type: "workflow"
    api_key_env: "DIFY_APP_API_KEY"
    inputs_template:
      query: "{input}"
      conversation_id: "{case_id}"
```

### 3.2 Custom HTTP Workflow (`http_workflow`)
Evaluates any arbitrary JSON REST endpoint or webhook pipeline:

```yaml
targets:
  - id: "custom-pipeline"
    connector: "http_workflow"
    url: "https://api.mycompany.com/pipeline/execute"
    method: "POST"
    headers:
      Content-Type: "application/json"
    json_payload:
      prompt: "{input}"
      session_id: "{case_id}"
    response_jsonpath: "$.data.completion"
```

### 3.3 In-Process Python Target (`python_target`)
Directly evaluate Python callables or classes in-process without network overhead:

```python
# target.py
def classify_text(input_data: dict) -> str:
    text = input_data.get("input", "")
    if "refund" in text.lower():
        return "BILLING"
    return "SUPPORT"
```

```yaml
targets:
  - id: "rule-based-classifier"
    connector: "python_target"
    entrypoint: "target:classify_text"
```

---

## 4. Writing a Custom Target

Custom targets subclass `Target` and implement `execute()` to return a `TargetResult`:

```python
import time
from typing import Any, Dict
from runport.targets.base import CostBasis, Target, TargetResult, TargetStatus, TargetType


class CustomRegexTarget(Target):
    """Custom target demonstrating regex matching."""

    def __init__(self, target_id: str = "regex-matcher") -> None:
        super().__init__(
            target_id=target_id,
            name="Regex Matcher",
            target_type=TargetType.PYTHON_CALLABLE,
            capabilities=["text"],
        )

    def execute(self, input_data: Dict[str, Any]) -> TargetResult:
        start_time = time.perf_counter()
        query = str(input_data.get("query", input_data.get("input", "")))

        # Custom logic
        output = "MATCH" if "urgent" in query.lower() else "NORMAL"
        elapsed_ms = (time.perf_counter() - start_time) * 1000.0

        return TargetResult(
            target_id=self.target_id,
            status=TargetStatus.SUCCESS,
            output_text=output,
            latency_ms=elapsed_ms,
            tokens_in=len(query.split()),
            tokens_out=1,
            cost_usd=None,
            cost_basis=CostBasis.UNAVAILABLE,
            metadata={"rule": "urgent_keyword"},
        )
```

---

## 5. Security & SSRF Defense

All HTTP-based connectors pass outbound URLs through [`validate_safe_url`](../src/runport/core/security.py):
- **Metadata Protection**: Requests to cloud metadata (`169.254.169.254`) are strictly blocked fail-closed.
- **Private Subnets**: Private RFC 1918 subnets (`10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16`) are blocked by default.
- **Loopback**: Local loopback (`127.0.0.1`) requires explicit `allow_localhost` enablement (e.g. for Ollama).

# Connectors & Evaluation Targets

Runport benchmarks any AI system — raw model endpoints, prompt wrappers, local models, or complex multi-step workflow graphs — through a unified `Target` protocol.

---

## Connector Status Matrix

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

## Writing a Custom Connector

Custom targets subclass `Target` and implement `execute()` to return a `TargetResult`. Here is a complete ~40-line example:

```python
import time
from typing import Any, Dict
from runport.targets.base import CostBasis, Target, TargetResult, TargetStatus, TargetType


class EchoUpperTarget(Target):
    """Custom target that transforms input text to uppercase."""

    def __init__(self, target_id: str = "echo-upper") -> None:
        super().__init__(
            target_id=target_id,
            name="Echo Uppercase Target",
            target_type=TargetType.PYTHON_CALLABLE,
            capabilities=["text"],
        )

    def execute(self, input_data: Dict[str, Any]) -> TargetResult:
        start_time = time.perf_counter()
        query = str(input_data.get("query", input_data.get("input", "")))

        # Your custom model invocation or API logic goes here
        transformed = query.upper()
        elapsed_ms = (time.perf_counter() - start_time) * 1000.0

        return TargetResult(
            target_id=self.target_id,
            status=TargetStatus.SUCCESS,
            output_text=transformed,
            latency_ms=elapsed_ms,
            tokens_in=len(query.split()),
            tokens_out=len(transformed.split()),
            cost_usd=None,
            cost_basis=CostBasis.UNAVAILABLE,
            metadata={"custom_flag": True},
        )
```

You can evaluate this target directly using `GenericRunner`:

```python
from runport.runs.executor import GenericRunner
from runport.runs.planner import create_execution_plan
from runport.storage.db import DatabaseManager

db = DatabaseManager(":memory:")
runner = GenericRunner(db=db)
target = EchoUpperTarget()

plan = create_execution_plan(["echo-upper"], "data/eval.jsonl", is_live=False)
results = runner.execute_plan(plan, {"echo-upper": target}, [{"id": "1", "query": "hello world"}])
print(results[0].output_text)  # "HELLO WORLD"
```

# Connectors & Evaluation Targets

Runport benchmarks any AI system — raw model endpoints, prompt wrappers, local models, or complex multi-step workflow graphs — through a unified `Target` protocol.

---

## Connector Status Matrix

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

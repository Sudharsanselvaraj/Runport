---
title: Langflow
description: Benchmark Langflow flows (experimental).
---

> [!WARNING]
> Experimental. The Langflow connector is a reference adapter and stays experimental until it passes the full offline contract test suite.

`LangflowConnector` calls `POST {base_url}/api/v1/run/{flow_id}` with a chat input and chat output.

```python
import os
from runport.connectors.langflow import LangflowConnector

target = LangflowConnector(
    target_id="rag-flow",
    name="RAG flow",
    base_url="https://langflow.example.com",
    flow_id="your-flow-id",
    api_key=os.environ.get("LANGFLOW_API_KEY"),
)
```

| Parameter | Default | Meaning |
|---|---|---|
| `base_url` | required | Langflow server |
| `flow_id` | required | The flow to run |
| `api_key` | `None` | Sent as the `x-api-key` header |
| `tweaks` | `None` | Component overrides passed to the flow |
| `pricing` | `None` | Without it cost is `UNAVAILABLE` |
| `timeout_seconds`, `max_retries` | `60.0`, `3` | Transport limits |

The case's `query` is sent as `input_value` with `input_type` and `output_type` set to `chat`. The answer is read from `outputs.0.outputs.0.results.message.text`.

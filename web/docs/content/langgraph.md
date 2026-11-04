---
title: LangGraph
description: Benchmark LangGraph assistants through the run endpoint (experimental).
---

> [!WARNING]
> Experimental. The LangGraph connector is a reference adapter and stays experimental until it passes the full offline contract test suite.

`LangGraphConnector` calls `POST {base_url}/runs/wait` on LangGraph Cloud or a self-hosted LangGraph Server and waits for the run to finish.

```python
import os
from runport.connectors.langgraph import LangGraphConnector

target = LangGraphConnector(
    target_id="research-agent",
    name="Research agent",
    base_url="https://your-langgraph-host",
    assistant_id="agent",
    api_key=os.environ.get("LANGGRAPH_API_KEY"),
)
```

| Parameter | Default | Meaning |
|---|---|---|
| `base_url` | required | Server root; `/runs/wait` is appended |
| `assistant_id` | required | The assistant (graph) to run |
| `api_key` | `None` | Sent as the `x-api-key` header |
| `pricing` | `None` | Without it cost is `UNAVAILABLE` |
| `timeout_seconds`, `max_retries` | `60.0`, `3` | Transport limits |

## Request and response

The case's `query` is sent as a single user message:

```json
{"assistant_id": "agent", "input": {"messages": [{"role": "user", "content": "{{query}}"}]}}
```

The answer is read from the last message's content (`messages.-1.content`). The connector is built on the [HTTP connector](/custom-http), so the same network safety rules apply.

---
title: Flowise
description: Benchmark Flowise chatflows and agent flows through the prediction API (experimental).
---

> [!WARNING]
> Experimental. The Flowise connector is a reference adapter and stays experimental until it passes the full offline contract test suite.

`FlowiseConnector` calls `POST {base_url}/api/v1/prediction/{chatflow_id}`.

```python
import os
from runport.connectors.flowise import FlowiseConnector

target = FlowiseConnector(
    target_id="docs-bot",
    name="Docs chatflow",
    base_url="https://flowise.example.com",
    chatflow_id="your-chatflow-id",
    api_key=os.environ.get("FLOWISE_API_KEY"),
)
```

| Parameter | Default | Meaning |
|---|---|---|
| `base_url` | required | Flowise server |
| `chatflow_id` | required | The chatflow to run |
| `api_key` | `None` | Sent as `Authorization: Bearer ...` |
| `override_config` | `None` | Sent as `overrideConfig` |
| `pricing` | `None` | Without it cost is `UNAVAILABLE` |
| `timeout_seconds`, `max_retries` | `60.0`, `3` | Transport limits |

The case's `query` is sent as `question`, and the answer is read from the response's `text` field.

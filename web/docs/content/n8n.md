---
title: n8n
description: Benchmark n8n workflows through a production webhook (experimental).
---

> [!WARNING]
> Experimental. The n8n connector is a reference adapter and stays experimental until it passes the full offline contract test suite.

`N8nConnector` posts each case to an n8n webhook trigger.

```python
from runport.connectors.n8n import N8nConnector

target = N8nConnector(
    target_id="triage-flow",
    name="Ticket triage",
    webhook_url="https://n8n.example.com/webhook/triage",
    output_path="output",   # the default
)
```

| Parameter | Default | Meaning |
|---|---|---|
| `webhook_url` | required | The production webhook URL |
| `auth_header` | `None` | Headers dict, for example a header-auth credential |
| `output_path` | `output` | Dotted path to the answer in the webhook response |
| `pricing` | `None` | Without it cost is `UNAVAILABLE` |
| `timeout_seconds`, `max_retries` | `60.0`, `3` | Transport limits |

## Request

The body carries the case's `query` and `payload` fields:

```json
{"query": "{{query}}", "payload": "{{payload}}"}
```

Configure the workflow's final node to respond with JSON that contains the answer at `output_path`. Network safety rules are the same as for the [HTTP connector](/custom-http#network-safety).

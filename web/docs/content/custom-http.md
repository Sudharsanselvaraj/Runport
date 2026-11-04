---
title: Custom HTTP providers
description: Benchmark any model, workflow or service behind an HTTP endpoint with the http_workflow connector.
---

`HttpWorkflowConnector` sends one request per case to any HTTP endpoint and extracts the answer from the JSON response. The workflow connectors (Flowise, Langflow, n8n, LangGraph) are built on it.

## Create a target

```python
from runport.connectors.http_workflow import HttpWorkflowConnector

target = HttpWorkflowConnector(
    target_id="support-bot",
    name="Support workflow",
    url="https://workflows.example.com/analyze",
    payload_template={"text": "{{query}}"},
    output_path="data.summary",
    timeout_seconds=30.0,
)
```

| Parameter | Default | Meaning |
|---|---|---|
| `url` | required | Endpoint to call |
| `method` | `POST` | HTTP method |
| `headers` | `None` | Request headers |
| `payload_template` | `None` | JSON body with `{{field}}` placeholders; without it the case is sent as-is |
| `output_path` | `None` | Dotted path to the answer in the response, for example `data.summary` or `messages.-1.content` |
| `pricing` | `None` | `TargetPricing`; without it cost is `UNAVAILABLE` |
| `timeout_seconds` | `30.0` | Per-request timeout |
| `max_retries` | `3` | Bounded retries on transient failures |
| `allow_private`, `allow_localhost`, `host_allowlist` | off | Network safety controls |

## Payload templates

Every `{{key}}` in the template is replaced with the case's value for `key` (strings, numbers and booleans). Placeholders use **double** braces.

```python
payload_template={"question": "{{query}}", "category": "{{programme_category}}"}
```

## Output paths

`output_path` walks the response JSON by key. A numeric segment indexes a list, and `-1` takes the last element.

## Network safety

Every outbound URL is validated before a request is made:

- Only `http` and `https` are allowed.
- Cloud metadata and link-local addresses (`169.254.0.0/16`) are always blocked.
- Loopback needs `allow_localhost=True`; private networks need `allow_private=True`; or list hosts in `host_allowlist`.

The repository's `examples/http-workflow/run.py` runs this connector against a local test server.

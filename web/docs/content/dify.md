---
title: Dify
description: Benchmark Dify chat and workflow applications with the supported dify connector.
---

`DifyConnector` benchmarks Dify **chat apps** and **workflow apps**, in blocking or streaming mode. It is a supported connector.

| App type | Endpoint | Telemetry recorded |
|---|---|---|
| Chat (`app_type="chat"`) | `POST /v1/chat-messages` | Token usage, `conversation_id`, `message_id` |
| Workflow (`app_type="workflow"`) | `POST /v1/workflows/run` | Total tokens, total steps, per-node executions |

## Create a target

```python
import os
from runport.connectors.dify import DifyConnector

target = DifyConnector(
    target_id="dify-support",
    name="Support assistant",
    api_key=os.environ["DIFY_API_KEY"],
    base_url="https://api.dify.ai/v1",   # or your self-hosted URL
    app_type="chat",                      # or "workflow"
    response_mode="blocking",             # or "streaming"
)
result = target.execute({"query": "What can this assistant do?"})
print(result.status, result.output_text)
```

| Parameter | Default | Meaning |
|---|---|---|
| `api_key` | required | Dify app API key; used only in the `Authorization` header |
| `base_url` | `https://api.dify.ai/v1` | Dify API root |
| `app_type` | `chat` | `chat` or `workflow` |
| `response_mode` | `blocking` | `blocking` or `streaming` |
| `user` | `runport-benchmark` | User identifier sent to Dify |
| `conversation_id` | `None` | Continue an existing conversation |
| `pricing` | `None` | `TargetPricing`; without it cost is `UNAVAILABLE` |
| `timeout_seconds`, `max_retries` | `30.0`, `3` | Transport limits |
| `allow_localhost`, `host_allowlist` | off | For self-hosted Dify on loopback or a named host |

## Inputs

- **Chat apps** send the case's `query` (or `input`) as the message and `inputs` (default `{}`) as app variables.
- **Workflow apps** send the case's `inputs` if present; otherwise every case field except `user` and `conversation_id` becomes an input.

## Keys

The key is used in the authorization header only. It is never returned in results or written to logs, and Dify responses are scrubbed of secrets before they are stored.

## Run it

Use the target with `GenericRunner`; see [Creating benchmarks](/creating-benchmarks). `examples/dify-workflow/run.py` shows a complete offline run.

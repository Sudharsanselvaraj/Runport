---
title: OpenAI-compatible providers
description: Benchmark any Chat Completions endpoint, hosted or self-hosted, with the openai_compat connector.
---

`OpenAICompatConnector` calls `POST {base_url}/chat/completions`. It works with OpenAI and with servers that implement the same API, such as vLLM and LocalAI.

## Create a target

```python
import os
from decimal import Decimal
from runport.connectors.openai_compat import OpenAICompatConnector
from runport.targets.base import TargetPricing

target = OpenAICompatConnector(
    target_id="gpt-small",
    name="OpenAI small model",
    model="your-model-id",
    base_url="https://api.openai.com/v1",
    api_key=os.environ["OPENAI_API_KEY"],      # read from the environment
    pricing=TargetPricing(
        input_usd_per_1m=Decimal("0.10"),
        output_usd_per_1m=Decimal("0.40"),
    ),
)
```

| Parameter | Default | Meaning |
|---|---|---|
| `model` | required | Model name sent in the request body |
| `base_url` | `https://api.openai.com/v1` | API root; `/chat/completions` is appended |
| `api_key` | `None` | Sent as `Authorization: Bearer ...` when set |
| `custom_headers` | `None` | Extra request headers |
| `default_params` | `None` | Body parameters merged into every request |
| `pricing` | `None` | `TargetPricing`; without it cost is `UNAVAILABLE` |
| `timeout_seconds` | `30.0` | Per-request timeout |
| `max_retries` | `3` | Bounded retries on transient failures |
| `allow_localhost`, `allow_private`, `host_allowlist` | off | SSRF controls; see [Custom HTTP providers](/custom-http#network-safety) |

> [!NOTE]
> The environment variable name for the key is yours to choose; Runport only reads `OPENROUTER_API_KEY` itself. Never put keys in `runport.yaml`: the loader rejects plain-text secrets.

## Input

Each case is passed to `execute()`. The connector uses `messages` if the case has them; otherwise it builds them from `query`, plus `system_prompt` when present. `temperature`, `max_tokens`, `top_p` and `response_format` in a case override the defaults for that request.

## Output and cost

The first choice's message content becomes `output_text`; `usage.prompt_tokens` and `usage.completion_tokens` become `tokens_in` and `tokens_out`. With `pricing` set and token counts reported, cost is `ESTIMATED`; otherwise it is `UNAVAILABLE`.

## Run it

Wrap the target in a plan and run it with `GenericRunner`; see [Creating benchmarks](/creating-benchmarks).

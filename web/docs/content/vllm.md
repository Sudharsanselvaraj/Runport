---
title: vLLM
description: Benchmark a vLLM server through its OpenAI-compatible API.
---

Runport has no vLLM-specific adapter. vLLM serves an OpenAI-compatible API, so you benchmark it with the [OpenAI-compatible connector](/openai-compatible).

## Point the connector at vLLM

```python
from runport.connectors.openai_compat import OpenAICompatConnector

target = OpenAICompatConnector(
    target_id="vllm-local",
    name="vLLM server",
    model="your-served-model-name",
    base_url="http://127.0.0.1:8000/v1",
    allow_localhost=True,   # required for a loopback address
)
```

> [!WARNING]
> Outbound URLs are checked for SSRF. Loopback addresses need `allow_localhost=True`; private network (RFC 1918) addresses need `allow_private=True` or an explicit `host_allowlist`. Cloud metadata addresses are always blocked.

> [!NOTE]
> Port `8000` is also the default port of `runport web`. If both run on one machine, start one of them on another port.

## Cost

A self-hosted server has no per-token bill. Leave `pricing` unset and results are booked as `UNAVAILABLE` at $0.00, or pass a `TargetPricing` if you want to model your own compute cost as an estimate.

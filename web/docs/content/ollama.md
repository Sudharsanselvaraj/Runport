---
title: Ollama
description: Benchmark local Ollama models at zero API cost.
---

`OllamaConnector` calls a local or private Ollama server's `/api/chat` endpoint. Local execution has no API cost, so results are booked as `UNAVAILABLE` at $0.00.

## Create a target

```python
from runport.connectors.ollama import OllamaConnector

target = OllamaConnector(
    target_id="llama-local",
    name="Llama via Ollama",
    model="llama3.1",
    base_url="http://127.0.0.1:11434",   # the default
)
```

| Parameter | Default | Meaning |
|---|---|---|
| `model` | required | Ollama model name |
| `base_url` | `http://127.0.0.1:11434` | Ollama server |
| `system_prompt` | `None` | System message added to every request |
| `format` | `None` | Set to `"json"` to request JSON output |
| `options` | `None` | Ollama model options merged into every request |
| `timeout_seconds` | `60.0` | Per-request timeout |
| `allow_localhost` | `True` | Loopback is allowed by default for this connector |
| `host_allowlist` | `None` | Explicit hosts to allow |

## Input

Cases may carry `messages`; otherwise the connector builds a user message from `query` (or `input`). A case can also override `system_prompt`, `format` and `options`.

## Why use it

Ollama targets need no key and spend nothing, which makes them a good choice for developing a benchmark before pointing it at a paid model. See [Creating benchmarks](/creating-benchmarks).

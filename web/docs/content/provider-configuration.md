---
title: Provider configuration
description: Where provider settings live today, and how to connect each kind of provider.
---

## Where configuration lives

| Provider | Configure with |
|---|---|
| OpenRouter | `OPENROUTER_API_KEY`, and the model ID on the command line |
| OpenAI-compatible, vLLM | `OpenAICompatConnector(...)` in Python |
| Ollama | `OllamaConnector(...)` in Python |
| Dify, Flowise, Langflow, n8n, LangGraph | The matching connector in Python |
| Any HTTP endpoint | `HttpWorkflowConnector(...)` in Python |

> [!NOTE]
> `runport.yaml` accepts a `targets` list (`id`, `type`, `endpoint`, `model`, `headers`, `options`), and it is validated when the workspace loads. In this release the CLI benchmark commands do not read it: they address OpenRouter models by ID. Other providers are configured by constructing connectors in Python, as shown on each provider's page.

## Connecting a provider

1. Put the key in the environment, never in `runport.yaml`.
2. Construct the connector with a `target_id`.
3. Add `pricing=TargetPricing(...)` if you want `ESTIMATED` costs; without it, costs are `UNAVAILABLE`.
4. For private or loopback hosts, set `allow_localhost`, `allow_private` or `host_allowlist`.
5. Run it with `GenericRunner`. See [Creating benchmarks](/creating-benchmarks).

## Provider pages

- [OpenAI-compatible providers](/openai-compatible)
- [OpenRouter](/openrouter)
- [Ollama](/ollama)
- [vLLM](/vllm)
- [Custom HTTP providers](/custom-http)

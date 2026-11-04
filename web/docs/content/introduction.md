---
title: Introduction
description: What Runport is, what it guarantees, and where to go next.
---

Runport is an open-source, local-first platform for benchmarking language models, prompt templates and orchestrated AI workflows. It runs on your machine, keeps every prompt, trace and ledger entry on your filesystem, and refuses to spend money it has not been told it may spend.

> [!NOTE]
> Runport is in **public alpha** (version 0.1.0). The budget ledger, guard order and CLI are stable; workflow connector coverage is still growing. Pages mark experimental features where they apply.

## What you can benchmark

Every system Runport evaluates implements one `Target` interface and returns one `TargetResult` shape, so a raw model and a multi-step workflow are measured the same way.

- **Model APIs**: OpenRouter, and any OpenAI-compatible Chat Completions server (OpenAI, vLLM, LocalAI and others). See [Model providers](/openai-compatible).
- **Local models**: Ollama, with no API cost. See [Ollama](/ollama).
- **Workflows**: Dify (supported); Flowise, Langflow, n8n and LangGraph (experimental); any HTTP endpoint. See [Integrations](/dify).
- **Code**: in-process Python callables and subprocess commands. See [Python integrations](/python-integrations).

## What Runport guarantees

- **Hard, fail-closed spend caps.** Total, pilot, per-run and per-case ceilings are checked before a request is sent. A request whose cost cannot be determined is booked as `UNRESOLVED`, and further live runs stay blocked until you reconcile it. See [Budget guardrails](/budget-guardrails).
- **Null is not 0.** Missing tokens, latency, confidence or cost stay empty (`None` / `UNAVAILABLE`); they are never filled with zero. See [Invariants](/invariants).
- **Ground truth over agreement.** Supervised metrics are computed against human-approved annotations. Agreement between models is reported as agreement, never as accuracy.
- **No telemetry.** Runport sends nothing anywhere except the requests you approve.

## Ways to use it

| Interface | Start it with | Use it for |
|---|---|---|
| CLI | `uv run runport` | Validating data, running benchmarks, managing the budget |
| Terminal UI | `uv run runport ui` | A full-screen Rich dashboard in the terminal |
| Web dashboard | `uv run runport web` | A local FastAPI + React dashboard on `127.0.0.1:8000` |
| Python API | `from runport...` | Wrapping your own models and workflows as targets |

## Next steps

1. [Install Runport](/installation).
2. Run the [Quickstart](/quickstart): an offline, $0.00 benchmark with no API key.
3. Read [Architecture](/architecture) to see how a request moves through the guards.

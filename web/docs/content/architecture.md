---
title: Architecture
description: How targets, the guarded runner, the ledger and the interfaces fit together.
---

Runport separates **what is being measured** (a target), **how it is run** (an execution plan and a guarded runner) and **how it is judged** (scorers and metrics). Everything is stored locally in SQLite.

## Components

| Module | Responsibility |
|---|---|
| `runport.targets` | The `Target` interface and `TargetResult`, the single result shape for every system |
| `runport.connectors` | Adapters for OpenAI-compatible APIs, Ollama, Dify, Flowise, Langflow, n8n, LangGraph, HTTP and Python |
| `runport.providers` | HTTP transport with bounded retries, and the OpenRouter adapter |
| `runport.runs` | `create_execution_plan`, `GenericRunner` and `ReplayRunner` |
| `runport.core` | Workspace config, budget service, approvers, live guard, SSRF checks, plugins |
| `runport.scorers` | Exact/regex match, classification, extraction, generation, LLM-judge, performance and statistics |
| `runport.storage` | The SQLite database in WAL mode and the spend ledger |
| `runport.observability` | Event log, trace export and budget audit |
| `runport.api`, `runport.tui`, `runport.cli` | The web API, the Rich terminal UI and the Typer CLI |

## The guard order

Every case in a run passes the same seven stages, in this order. No stage can be skipped.

1. **Authorization check.** Live runs are refused while any `UNRESOLVED` ledger entry exists, and need an approval bound to the plan fingerprint.
2. **Privacy gate.** The whole batch is scanned before anything is sent; a forbidden field in any case aborts the run.
3. **Preflight budget and context check.** The worst-case cost of the request is checked against every ceiling.
4. **Transport execution.** The target is called; HTTP transports retry only transient statuses, a bounded number of times.
5. **Strict validation.** Empty or whitespace output becomes `invalid_output`.
6. **Persistence.** The run and per-case results are written to SQLite.
7. **Spend booking.** Cost is booked as `ACTUAL`/`ESTIMATED`, as `$0.00 UNAVAILABLE` for local execution, or as `UNRESOLVED` when a billed request has unknown cost.

Stages 1, 3 and 7 apply to live plans; replay and offline plans skip approval and book nothing. See [Runs and plans](/runs-and-plans).

## Storage

All state lives in one SQLite database in WAL mode (`data/runport.db` by default): evaluation runs, per-case results, the append-only spend ledger and the event log. Reports and exports go to `reports/`. Nothing is uploaded.

## Interfaces

The CLI, the terminal UI and the web dashboard all read the same database. The web server binds to `127.0.0.1` by default and refuses a non-loopback host unless `RUNPORT_API_TOKEN` is set. See [Web and terminal dashboards](/dashboards).

## Extending Runport

Third-party targets and scorers are discovered through Python entry points (`runport.targets`, `runport.scorers`, `runport.plugins`). See [Plugins](/plugins).

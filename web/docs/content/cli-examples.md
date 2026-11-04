---
title: Examples
description: Common CLI workflows, from a first offline run to a reconciled live run.
---

## First run, offline

```bash
uv run runport init
uv run runport validate-dataset data/evaluation/synthetic_seed_eval.jsonl
uv run runport api-preflight
uv run runport benchmark --replay
```

## Check a dataset before you trust it

```bash
uv run runport validate-dataset my_cases.jsonl
uv run runport annotate my_cases.jsonl --reviewer "Your Name"
```

## A live run under caps

```bash
uv run runport budget status
uv run runport benchmark --model google/gemini-3.5-flash-lite --split DEV          # explain only
uv run runport benchmark --model google/gemini-3.5-flash-lite --split DEV --live   # asks for the typed phrase
```

## Compare two runs

```bash
uv run runport compare-runs RUN_A RUN_B
```

Run IDs are printed at the end of each benchmark and listed in the web dashboard.

## Recover from unresolved spend

```bash
uv run runport budget status
uv run runport budget reconcile --transaction-id tx-1a2b3c4d5e6f --amount-usd 0.0042 --note "dashboard 2026-11-04"
```

## Export traces for review

```bash
uv run runport export-traces -f zip
uv run runport export-traces -f jsonl --status INVALID_OUTPUT --status ERROR
```

## Clean up dry runs

```bash
uv run runport budget purge-simulated
```

## In CI

Replay runs need no key and book $0.00:

```bash
uv sync --extra dev
uv run pytest
uv run runport benchmark --replay
```

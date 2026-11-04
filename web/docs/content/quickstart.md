---
title: Quickstart
description: Initialize a workspace, validate a dataset and run an offline benchmark with no API key and $0.00 spend.
---

Everything on this page runs offline. No API key is needed and no request leaves your machine.

## 1. Initialize a workspace

```bash
uv run runport init
```

This writes `runport.yaml` (budget ceilings, approval mode, privacy settings), creates `data/evaluation/` and `reports/`, and initializes the SQLite ledger at `data/runport.db`. Use `--dir` to choose a directory, `--name` to name the workspace and `--force` to overwrite an existing `runport.yaml`. See [Workspace file](/workspace-file).

## 2. Validate a dataset

```bash
uv run runport validate-dataset data/evaluation/synthetic_seed_eval.jsonl
```

Runport checks every record against the case schema, counts records per split (`TRAIN`, `DEV`, `TEST`), reports how many records may be sent to external providers (only `PUBLIC` and `SYNTHETIC`), and runs cross-split leakage detection. See [Datasets](/datasets).

## 3. Run the offline preflight

```bash
uv run runport api-preflight
```

It reports whether an API key is configured, without showing it and without sending anything.

## 4. Run a replay benchmark

```bash
uv run runport benchmark --replay --dataset data/evaluation/synthetic_seed_eval.jsonl
```

A replay run is stored with provenance `REPLAYED` and books `$0.00`.

> [!IMPORTANT]
> The CLI replay mode verifies the pipeline (dataset loading, storage, reporting) end to end. It does not measure a model: it replays the dataset's own records and records fixed summary values. To replay recorded model outputs, use `ReplayRunner` with a fixtures file; see [Reproducibility](/reproducibility#deterministic-replay).

Without `--replay` or `--live`, `runport benchmark` only explains what it would do and sends nothing.

## 5. Look at the results

```bash
uv run runport budget status
uv run runport web
```

`budget status` shows ceilings, spend and remaining balances. `runport web` starts the local dashboard at `http://127.0.0.1:8000`. See [Web and terminal dashboards](/dashboards).

## 6. Optional: a live run

Live runs send real requests to OpenRouter and are tracked against your ceilings.

```bash
export OPENROUTER_API_KEY="..."
uv run runport benchmark --live --model google/gemini-3.5-flash-lite
```

Before any request, Runport asks you to type an exact confirmation phrase. See [Executing benchmark runs](/executing-runs).

## Next

- [Creating benchmarks](/creating-benchmarks) for your own models and workflows.
- [Budget guardrails](/budget-guardrails) before your first live run.

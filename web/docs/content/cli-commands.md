---
title: Commands
description: Every runport command and option in this release.
---

Budget subcommands are on [Budget commands](/cli-budget).

## init

Create `runport.yaml`, `data/evaluation/`, `reports/` and the SQLite database.

```bash
runport init [--dir PATH] [--name TEXT] [--force]
```

| Option | Default | Meaning |
|---|---|---|
| `-d`, `--dir` | current directory | Where to create the workspace |
| `-n`, `--name` | `runport-workspace` | Workspace name |
| `-f`, `--force` | off | Overwrite an existing `runport.yaml` |

## validate-dataset

```bash
runport validate-dataset [DATASET_PATH] [--check-leakage | --no-check-leakage]
```

| Argument / option | Default | Meaning |
|---|---|---|
| `DATASET_PATH` | `data/evaluation/synthetic_seed_eval.jsonl` | JSONL dataset |
| `--check-leakage` / `--no-check-leakage` | on | Cross-split leakage and n-gram overlap detection |

## annotate

```bash
runport annotate [DATASET_PATH] [--reviewer TEXT]
```

Lists each case's ground-truth verification status and citation. Read-only in this release. `-r`, `--reviewer` defaults to `Principal Reviewer`. See [Ground truth](/ground-truth).

## benchmark

```bash
runport benchmark [--model ID] [--dataset FILE] [--split TEST|DEV|ALL] [--live | --replay [--fixtures FILE]]
```

| Option | Default |
|---|---|
| `-m`, `--model`, `--target` | `google/gemini-3.5-flash-lite` |
| `-d`, `--dataset` | `data/evaluation/synthetic_seed_eval.jsonl` |
| `-s`, `--split` | `TEST` |
| `--live` | off: without it nothing is sent |
| `--replay` | off |
| `-f`, `--fixtures` | the dataset file (replay only: recorded outputs to score) |

See [Executing benchmark runs](/executing-runs).

## benchmark-rag

```bash
runport benchmark-rag [--model ID] [--dataset FILE] [--split S] [--live] [--compare-with ID] [--top-k N] [--exclude-defective | --include-all]
```

Defaults: model `google/gemini-3.5-flash-lite`, dataset `data/evaluation/verified_rag_benchmark.jsonl`, split `TEST`, top-k `2`, `--exclude-defective`. See [RAG benchmarks](/rag-benchmarks).

## smoke-test

```bash
runport smoke-test [--model ID] [--cases N] [--live]
```

Defaults: model `openai/gpt-4.1-nano`, cases `2`. Offline it verifies a synthetic plan; with `--live` it asks for confirmation and, in this release, sends nothing after approval.

## compare-runs

```bash
runport compare-runs RUN_A RUN_B
```

Both run IDs are required. See [Comparing runs](/comparing-runs).

## models

```bash
runport models roster
runport models list
```

Both show the registered model candidates and their attributes (`list` is the same view as `roster`).

## api-preflight

```bash
runport api-preflight
```

Reports whether `OPENROUTER_API_KEY` is available and where it came from, without showing it and without sending a request.

## export-traces

```bash
runport export-traces [--format zip|jsonl|csv] [--model KEY]... [--run ID]... [--task TASK] [--status S]... [--out-dir PATH]
```

| Option | Default | Meaning |
|---|---|---|
| `-f`, `--format` | `zip` | `jsonl`, `csv` or `zip` (per-model files, a comparison file and a manifest) |
| `-m`, `--model` | all | Limit to a model key (repeatable) |
| `-r`, `--run` | all | Limit to a run ID (repeatable) |
| `-t`, `--task` | all | Task filter, for example `classification`, `benchmark`, `rag` |
| `-s`, `--status` | all | `OK`, `INVALID_OUTPUT` or `ERROR` (repeatable) |
| `--out-dir` | `reports/exports` | Destination |

## import-traces

```bash
runport import-traces EXPORT_FILE [--output-dir PATH] [--min-confidence FLOAT]
```

Ingests a redacted Langfuse JSON or CSV trace export and diagnoses candidate RAG failure modes. `-c`, `--min-confidence` defaults to `0.5`; `-o`, `--output-dir` writes CSV and Markdown reports.

## ui

```bash
runport ui [--web] [--port N]
```

The full-screen terminal UI, or the web dashboard with `--web` (port default `8000`).

## web

```bash
runport web [--host HOST] [--port N] [--reload | --no-reload]
```

Defaults: host `127.0.0.1`, port `8000`, no reload. A non-loopback host requires `RUNPORT_API_TOKEN`. See [Dashboards](/dashboards).

## welcome

```bash
runport welcome
```

The interactive welcome screen.

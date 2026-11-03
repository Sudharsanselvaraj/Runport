# CLI Reference

Runport provides a structured CLI built with Typer.

---

## Global Options

```text
Usage: runport [OPTIONS] COMMAND [ARGS]...

Options:
  -i, --interactive       Launch interactive terminal UI.
  --install-completion    Install completion for the current shell.
  --show-completion       Show completion for the current shell.
  --help                  Show this message and exit.
```

---

## Subcommands

### `runport init`
Initialize a new Runport workspace configuration and directory tree.

```bash
runport init [-d, --dir <path>] [-n, --name <str>] [-f, --force]
```
- `-d, --dir`: Directory in which to initialize workspace (default: current directory).
- `-n, --name`: Workspace name (default: `runport-workspace`).
- `-f, --force`: Overwrite existing configuration file.

---

### `runport validate-dataset`
Validate evaluation dataset schemas, confidentiality boundaries, and cross-split leakage.

```bash
runport validate-dataset [dataset_path] [--check-leakage | --no-check-leakage]
```
- `dataset_path`: Path to JSONL evaluation dataset file (default: `data/evaluation/synthetic_seed_eval.jsonl`).
- `--check-leakage`: Perform cross-split (train/dev/test) leakage and n-gram overlap detection.

---

### `runport benchmark`
Benchmark a candidate model with REAL requests (typed approval required) or offline replay.

```bash
runport benchmark [-m, --model <str>] [-d, --dataset <file>] [-s, --split <str>] [--live] [--replay]
```
- `-m, --model`: Target candidate model ID to evaluate (default: `google/gemini-3.5-flash-lite`).
- `-d, --dataset`: Path to evaluation dataset JSONL.
- `-s, --split`: Evaluation split to benchmark: `TEST`, `DEV`, or `ALL` (default: `TEST`).
- `--live`: Send real requests to OpenRouter (prompts for cryptographic confirmation).
- `--replay`: Execute offline using deterministic replay targets ($0.00 spend).

---

### `runport benchmark-rag`
Benchmark candidate models on decoupled retrieval, generation, and end-to-end RAG metrics.

```bash
runport benchmark-rag [--live] [--dataset <file>]
```

---

### `runport compare-runs`
Compare two evaluation benchmark runs side by side.

```bash
runport compare-runs <run_a> <run_b>
```
- `run_a`: Run ID of the baseline evaluation run.
- `run_b`: Run ID of the comparison evaluation run.

---

### `runport budget`
Budget ledger, ceilings, and spend tracking commands.

```bash
runport budget status
runport budget audit
runport budget policy
runport budget raise-pilot-ceiling
runport budget reconcile
runport budget purge-simulated
```
- `status`: Display current spend ledger, remaining balances, and local policy ceilings.
- `audit`: Reconcile ledger with stored results; generate audit report.
- `policy`: Show effective ceilings and audit trail of operator ceiling changes.
- `raise-pilot-ceiling`: Operator-authorized pilot ceiling change with interactive phrase.
- `reconcile`: Resolve an unresolved-spend entry with an amount read from provider dashboard.
- `purge-simulated`: Delete all simulated (dry-run) ledger rows (backs up database first).

---

### `runport models`
Model portfolio catalog and validation commands.

```bash
runport models list
runport models validate
```

---

### `runport api-preflight`
Report whether the API key is available WITHOUT showing it and WITHOUT sending any request.

```bash
runport api-preflight
```

---

### `runport export-traces`
Export stored trace records (redacted, local only).

```bash
runport export-traces [-f, --format <zip|jsonl|csv>] [-m, --model <str>] [-r, --run <str>] [-s, --status <str>] [--out-dir <path>]
```
- `-f, --format`: Export archive format (`zip`, `jsonl`, or `csv`; default: `zip`).
- `--out-dir`: Destination folder (default: `reports/exports`).

---

### `runport ui`
Launch the interactive terminal UI (or web dashboard with `--web`).

```bash
runport ui [--web] [--port <int>]
```

---

### `runport web`
Start the Runport web dashboard and REST API service.

```bash
runport web [--host <str>] [--port <int>] [--reload]
```
- `--host`: Host interface to bind to (default: `127.0.0.1`).
- `--port`: Port to listen on (default: `8000`).
- `--reload`: Enable auto-reload for development.

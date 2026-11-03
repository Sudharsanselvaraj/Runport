# Quickstart Guide

Get up and running with Runport in under two minutes.

---

## 1. Installation

### Requirements
- **Python**: 3.11, 3.12, or 3.13
- **uv** (recommended) or standard `pip`

### Install with uv
```bash
# Clone the repository
git clone https://github.com/Sudharsanselvaraj/runport.git
cd runport

# Install dependencies including dev and report tools
uv sync --extra dev --extra report
```

### Install with pip
```bash
pip install -e .
```

---

## 2. Initialize a Workspace

Initialize your local workspace configuration and data directory structure:

```bash
uv run runport init
```

This generates:
- `runport.yaml`: Active workspace configuration defining spend ceilings, privacy gates, and connectors.
- `data/`: Local evaluation datasets and trace stores.
- `.runport/`: Local SQLite WAL ledger (`runport.db`).

---

## 3. Validate Evaluation Data

Before benchmarking, validate dataset integrity, schema conformity, and cross-split leakage:

```bash
uv run runport validate-dataset data/evaluation/synthetic_seed_eval.jsonl
```

Runport verifies:
- Strict JSONL syntax and required target columns.
- Split cleanliness (`TEST`, `DEV`, `TRAIN`).
- Overlap detection to prevent test-set contamination.
- Forbidden identifier redaction.

---

## 4. Run an Offline Replay Benchmark

Execute a benchmark immediately without spending money or providing an API key using the deterministic replay engine:

```bash
uv run runport benchmark --replay --dataset data/evaluation/synthetic_seed_eval.jsonl
```

Key guarantees:
- **$0.00 Spend**: Provenance is recorded as `REPLAYED`.
- **Zero Network Traffic**: Complete offline execution.
- Generates accuracy, Wilson 95% score intervals, and latency percentiles.

---

## 5. Live Evaluation (Under Spend Caps)

To evaluate live candidate models (via OpenRouter or supported workflow endpoints):

1. Set your API key in the shell:
   ```bash
   export OPENROUTER_API_KEY="sk-or-v1-..."
   ```

2. Run preflight verification (checks key presence without touching the network):
   ```bash
   uv run runport api-preflight
   ```

3. Execute evaluation with explicit `--live` flag and spend cap enforcement:
   ```bash
   uv run runport benchmark --live --model google/gemini-3.5-flash-lite
   ```

Runport prompts for an interactive cryptographic plan confirmation before sending any HTTP request.

---

## 6. Inspect Budget & Telemetry

Check your ledger balance, active spend ceilings, and reconciliation status:

```bash
uv run runport budget status
```

---

## 7. Launch Dashboards

### Interactive Terminal UI (Rich)
```bash
uv run runport ui
```

### Local Web Dashboard (FastAPI + React)
```bash
uv run runport web
```
Open [http://127.0.0.1:8000](http://127.0.0.1:8000) in your browser.

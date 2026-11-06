# Quickstart Guide

Get up and running with Runport in under two minutes.

---

## 1. Installation

Runport requires **Python 3.11, 3.12, or 3.13**.

### Option A: Install via uv (Recommended)

[`uv`](https://docs.astral.sh/uv/) provides fast, reliable dependency resolution:

```bash
# Global CLI install
uv tool install runport

# Or clone and run locally
git clone https://github.com/Sudharsanselvaraj/runport.git
cd runport
uv sync --extra dev --extra report
```

### Option B: Install via pip

```bash
pip install runport
```

---

## 2. Initialize a Workspace

Set up your local configuration, data directories, and SQLite WAL ledger:

```bash
uv run runport init
```

This generates:
- `runport.yaml`: Active workspace settings defining budget caps, connectors, and privacy rules.
- `.runport/runport.db`: Local append-only SQLite WAL ledger.
- `data/`: Local evaluation datasets and trace stores.

---

## 3. Validate Evaluation Data

Before benchmarking, validate dataset integrity, schema conformity, and cross-split leakage:

```bash
uv run runport validate-dataset data/evaluation/synthetic_seed_eval.jsonl
```

Runport verifies:
- JSONL syntax and required target columns (`case_id`, `input_text`, `expected_output`).
- Split cleanliness (`TRAIN`, `DEV`, `TEST`).
- Overlap detection preventing test-set contamination.
- Forbidden PII identifiers.

---

## 4. Run an Offline Replay Benchmark ($0.00 Spend)

Test your setup immediately without spending a cent or configuring API keys using the deterministic offline replay engine:

```bash
uv run runport benchmark --replay --dataset data/evaluation/synthetic_seed_eval.jsonl
```

Key guarantees:
- **$0.00 Spend**: Provenance is recorded as `REPLAYED`.
- **Zero Network Traffic**: Complete offline execution.
- Evaluates test cases and computes statistical metrics using recorded ground truth.

---

## 5. Live Evaluation (Under Fail-Closed Spend Caps)

To evaluate live candidate models (via OpenRouter or supported workflow endpoints):

1. **Set your API key**:
   ```bash
   export OPENROUTER_API_KEY="sk-or-v1-..."
   ```

2. **Verify credentials offline**:
   ```bash
   uv run runport api-preflight
   ```

3. **Execute live evaluation**:
   ```bash
   uv run runport benchmark --live --model google/gemini-3.5-flash-lite
   ```

Runport computes a cryptographic SHA-256 plan fingerprint and prompts for interactive typed confirmation before dispatching any request.

---

## 6. Launch the Local Interfaces

### Terminal UI Dashboard (`runport ui`)
```bash
uv run runport ui
```
Full-screen dashboard featuring CPU/memory gauges, real-time inference streams, model catalog browsers, and budget monitors.

### Web Dashboard (`runport web`)
```bash
uv run runport web
```
Opens the React + FastAPI web dashboard at **http://127.0.0.1:8000** for interactive plan previews, confusion matrices, and trace analysis.

---

## 7. Evaluate with Pytest & Python SDK

You can also use Runport directly in Python test suites:

```python
import pytest
from runport.scorers.classification import ClassificationReportScorer
from runport.scorers.stats import wilson


def test_intent_classification():
    predictions = ["SUPPORT", "BILLING", "SUPPORT"]
    ground_truth = ["SUPPORT", "BILLING", "SALES"]

    scorer = ClassificationReportScorer(allowed_labels=["SUPPORT", "BILLING", "SALES"])
    report = scorer.compute_report(predictions, ground_truth)
    lo, hi = wilson(report.valid_cases, report.total_cases)

    assert report.accuracy >= 0.60
    assert lo > 0.20
```

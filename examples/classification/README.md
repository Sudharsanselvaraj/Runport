# Offline Classification Benchmark Example

This example demonstrates single-label intent/ticket classification using synthetic data and Runport's `GenericRunner`.

---

## Files
- `synthetic_data.jsonl`: 5 synthetic customer support queries with ground truth category labels.
- `run.py`: Minimal execution script running a local rule-based classifier against the dataset.

---

## How to Run

```bash
uv run python examples/classification/run.py
```

Runs completely offline in `<0.1s` and outputs per-case results with Wilson 95% binomial confidence intervals.

# Deterministic Replay Demo

Demonstrates offline execution of previously recorded model interactions using Runport's `ReplayRunner`.

---

## Files
- `fixtures.jsonl`: Pre-recorded synthetic completions with token counts and latencies.
- `run.py`: Executes cases against the replay runner, guaranteeing `$0.00` spend and `REPLAYED` provenance.

---

## How to Run

```bash
uv run python examples/replay-demo/run.py
```

Runs completely offline in `<0.05s`.

# In-Process Python Callable Target Example

Demonstrates benchmarking an in-process Python function or agent chain directly using Runport's `PythonCallableTarget` without HTTP or network overhead.

---

## Files
- `run.py`: Evaluates a native Python function across test records, tracking latency and outputs with zero spend.

---

## How to Run

```bash
uv run python examples/python-callable/run.py
```

Runs completely offline in `<0.05s`.

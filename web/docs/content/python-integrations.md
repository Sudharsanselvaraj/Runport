---
title: Python integrations
description: Benchmark in-process Python functions and command-line programs as targets.
---

Two targets run your own code: `PythonCallableTarget` for a function in the same process, and `SubprocessTarget` for any command-line program. Neither makes network calls, and both book $0.00 unless you give them a price.

## Python callables

```python
from runport.connectors.python_target import PythonCallableTarget

def pipeline(case: dict) -> dict:
    text = case.get("text", "")
    return {"output": text.strip().title()}

target = PythonCallableTarget(target_id="title-case", name="Title-case pipeline", func=pipeline)
print(target.execute({"text": "hello world"}).output_text)   # Hello World
```

| Parameter | Default | Meaning |
|---|---|---|
| `func` | required | A callable taking the case dict |
| `pricing` | `None` | Optional `TargetPricing` |
| `timeout_seconds` | `30.0` | Time limit |

The return value becomes `output_text`: for a dict, its `output` or `answer` key, or else the whole dict as JSON; for anything else, `str(value)`.

## Command-line programs

```python
from runport.connectors.python_target import SubprocessTarget

target = SubprocessTarget(
    target_id="cli-classifier",
    name="CLI classifier",
    command=["python", "classify.py"],
)
```

The case is written to the program's standard input as JSON; trimmed standard output becomes `output_text`. Pass `env` to set environment variables for the process.

## Run them

Use either target with `GenericRunner`; see [Creating benchmarks](/creating-benchmarks).

```bash
uv run python examples/python-callable/run.py
```

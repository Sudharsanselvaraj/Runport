---
title: Creating benchmarks
description: Wrap a model, workflow or function as a target and run it through the guarded runner in Python.
---

The CLI benchmarks OpenRouter models. Everything else (connectors, workflows, local models, your own code) is benchmarked from Python with `GenericRunner`, which applies the same guard order as the CLI.

## 1. Choose or write a target

Use a connector from `runport.connectors`, or subclass `Target`:

```python
import time
from typing import Any, Dict
from runport.targets.base import CostBasis, Target, TargetResult, TargetStatus, TargetType


class EchoUpperTarget(Target):
    def __init__(self, target_id: str = "echo-upper") -> None:
        super().__init__(
            target_id=target_id,
            name="Echo Uppercase Target",
            target_type=TargetType.PYTHON_CALLABLE,
            capabilities=["text"],
        )

    def execute(self, input_data: Dict[str, Any]) -> TargetResult:
        start = time.perf_counter()
        query = str(input_data.get("query", ""))
        return TargetResult(
            target_id=self.target_id,
            status=TargetStatus.SUCCESS,
            output_text=query.upper(),
            latency_ms=(time.perf_counter() - start) * 1000.0,
            cost_usd=None,                       # unknown stays None
            cost_basis=CostBasis.UNAVAILABLE,
        )
```

`execute()` receives one case (a dict from your dataset) and returns one `TargetResult`. Leave fields you cannot measure as `None`; see [Invariants](/invariants#1-null-is-not-0).

## 2. Build a plan

```python
from pathlib import Path
from runport.runs.planner import create_execution_plan

plan = create_execution_plan(["echo-upper"], Path("data/eval.jsonl"), is_live=False)
```

The plan hashes the dataset and computes a fingerprint. See [Runs and plans](/runs-and-plans).

## 3. Run it

```python
import json
from runport.runs.executor import GenericRunner
from runport.storage.db import DatabaseManager

db = DatabaseManager("data/runport.db")
db.init_db()
runner = GenericRunner(db=db)

cases = [json.loads(line) for line in Path("data/eval.jsonl").read_text().splitlines() if line.strip()]
results = runner.execute_plan(plan, {"echo-upper": EchoUpperTarget()}, cases)

for r in results:
    print(r.run_id, r.successful_cases, r.failed_cases, r.invalid_cases, r.mean_latency_ms)
```

`execute_plan` returns one `GenericRunResult` per target, and writes the run and its per-case results to the database.

## 4. Score the outputs

`GenericRunner` records whether each case completed, not whether it was right. Score correctness by applying a scorer to `case_results`:

```python
from runport.scorers.match import ExactMatchScorer

scorer = ExactMatchScorer(ignore_case=True, normalize_whitespace=True)
for case, res in zip(cases, results[0].case_results):
    print(case["id"], scorer.score(res.output_text, case.get("expected_answer")).score)
```

> [!IMPORTANT]
> For `GenericRunner` runs, the stored `accuracy` and `overall_score` columns are 1.0 when a case completed with status `success` and 0.0 otherwise. They are completion rates, not correctness. See [Understanding results](/understanding-results).

## Live plans

Pass `is_live=True` to `create_execution_plan` and an approver to `execute_plan`. The runner then refuses to start while `UNRESOLVED` spend exists, checks every case against the budget, and books spend. See [Approval policies](/approval-policies).

## Runnable examples

The repository ships offline examples you can run as-is:

```bash
uv run python examples/python-callable/run.py
uv run python examples/classification/run.py
uv run python examples/replay-demo/run.py
```

---
title: Runs and plans
description: How an execution plan is built and fingerprinted, approved, and turned into a stored run.
---

Runport has no separate "experiment" object. An experiment is an **execution plan** (what will run, on which data, under which cap) executed into one **run** per target.

## Execution plans

`create_execution_plan` reads the dataset, hashes it and returns an `ExecutionPlan`:

```python
from decimal import Decimal
from pathlib import Path
from runport.runs.planner import create_execution_plan

plan = create_execution_plan(
    target_ids=["my-target"],
    dataset_path=Path("data/evaluation/synthetic_seed_eval.jsonl"),
    budget_cap_usd=Decimal("1.00"),   # default 1.00
    prompt_template=None,             # hashed when given
    is_live=False,
)
print(plan.plan_id, plan.fingerprint)
```

| Field | Meaning |
|---|---|
| `plan_id` | `plan-<first 8 of dataset hash>-<n>targets` |
| `target_ids` | Targets the plan covers |
| `dataset_hash` | SHA-256 over the dataset's non-blank lines |
| `total_cases` | Number of non-blank lines |
| `budget_cap_usd` | Cap bound into the plan |
| `prompt_template_hash` | SHA-256 of the prompt template, or `none` |
| `is_live` | Whether the plan sends real requests |
| `fingerprint` | SHA-256 over the fields above (targets sorted) |

## The plan fingerprint

The fingerprint binds the sorted target IDs, dataset hash, case count, budget cap and prompt-template hash. Change any of them and the fingerprint changes. Approvers check the fingerprint they are given against the one recomputed for the plan, so an approval cannot be reused for a different plan. See [Approval policies](/approval-policies).

## Runs

`GenericRunner.execute_plan(plan, targets, cases, approver=None)` executes the plan once per target and returns a `GenericRunResult` for each:

| Field | Meaning |
|---|---|
| `run_id` | Stored run identifier |
| `plan_id`, `plan_fingerprint` | The plan this run executed |
| `total_cases`, `successful_cases`, `failed_cases`, `invalid_cases` | Case counts by outcome |
| `total_spend_usd` | Spend booked for the run |
| `mean_latency_ms` | Mean latency across cases |
| `case_results` | One `TargetResult` per case |

Each run and its per-case results are saved to SQLite. Offline plans are stored as dry runs (`is_dry_run = 1`), which `runport budget purge-simulated` can remove.

## Live versus offline

| | Offline plan (`is_live=False`) | Live plan (`is_live=True`) |
|---|---|---|
| Approval | Not required | Required; refused while `UNRESOLVED` spend exists |
| Budget preflight | Skipped | Every case |
| Spend booking | None | Every case |
| Stored as | Dry run | Live run |

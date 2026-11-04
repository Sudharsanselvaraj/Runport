---
title: Classification
description: Label accuracy, per-class metrics, calibration and DEV-only threshold selection.
---

Runport's classification tools live in `runport.scorers.classification` (scorers) and `runport.classification` (metrics, validators, threshold selection and a guarded `ClassificationRunner`).

## Multiclass metrics

`compute_classification_metrics` takes `ClassificationItem(expected, predicted, exclusion_reason=None)` items:

```python
from runport.classification.metrics import ClassificationItem, compute_classification_metrics

m = compute_classification_metrics([
    ClassificationItem(expected="BILLING", predicted="BILLING"),
    ClassificationItem(expected="TECHNICAL", predicted=None),   # invalid output
    ClassificationItem(expected=None, predicted="BILLING"),     # unlabeled: not scored
])
print(m.accuracy, m.invalid_rate, m.per_class, m.confusion)
```

- Items with an `exclusion_reason` and items with no expected label are not scored; they are counted in `n_excluded` and `n_unlabeled`.
- An invalid output (`predicted=None`) stays in the denominator and counts as wrong.
- With nothing to score, `accuracy` is `None`, not `0`.

## Output validation

`validate_classification_output` classifies malformed outputs with an explicit reason: `EMPTY_OUTPUT`, `UNKNOWN_LABEL`, `EXTRA_TEXT`, `WRONG_CASE`, `CODE_FENCE`, `INVALID_JSON`, `NOT_OBJECT`, `MISSING_KEY`, `EXTRA_KEYS`, `NON_BOOLEAN`.

## Calibration

- `BrierScoreScorer` scores one binary probability against its label.
- `brier_multiclass` and `expected_calibration_error` (10 bins by default) summarize calibration over a set. Both return `None` when probabilities are unavailable; probabilities are never imputed.

## Thresholds are chosen on DEV only

When a target returns probabilities, `runport.classification.threshold` picks a decision threshold and freezes it:

```python
from runport.classification.threshold import select_threshold_on_dev, evaluate_held_out

frozen = select_threshold_on_dev(dev_items)       # every item must have split == DEV
report = evaluate_held_out(test_items, frozen)    # applied unchanged
```

`select_threshold_on_dev` maximizes F1 (ties: higher precision, then the higher threshold) and raises if any item is not from `DEV`. The frozen threshold is then applied unchanged to held-out data; 0.5 is always reported as a reference. `roc_auc` is also available.

## Splitting by group

`runport.classification.splits.assign_group_splits` assigns whole groups of related cases to one split, and `find_group_leaks` reports groups that appear in more than one split.

## Example

```bash
uv run python examples/classification/run.py
```

Runs a rule-based classifier on five synthetic support tickets offline and prints per-case results with Wilson 95% intervals.

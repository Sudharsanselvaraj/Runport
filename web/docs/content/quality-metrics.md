---
title: Quality evaluation
description: Accuracy, per-class F1, Wilson and bootstrap intervals, multiple-comparison correction and agreement.
---

Quality metrics are computed against human-approved ground truth. The helpers below are in `runport.scorers.stats` and `runport.classification.metrics`.

## Accuracy

```text
accuracy = correct / scored
```

`scored` counts every labelled, non-excluded case. Invalid, unparsable or timed-out outputs stay in the denominator and count as wrong; they are never silently dropped. With nothing to score, accuracy is `None`.

## Precision, recall and F1

For each class c:

```text
precision_c = TP_c / (TP_c + FP_c)
recall_c    = TP_c / (TP_c + FN_c)
F1_c        = 2 · precision_c · recall_c / (precision_c + recall_c)
```

An invalid output counts as a false negative for its true class. `stats.prf(tp, fp, fn)` returns `NaN` for a ratio with a zero denominator rather than inventing a value.

## Wilson intervals

Proportions such as accuracy carry a 95% Wilson score interval, which behaves well for small samples and proportions near 0 or 1:

```python
from runport.scorers.stats import wilson
print(wilson(42, 50))   # (low, high), clamped to [0, 1]
```

With `n = 0` the interval is `(NaN, NaN)`.

## Bootstrap intervals

For continuous statistics such as mean latency or cost, `boot_ci(values, stat, label)` returns a 95% percentile-bootstrap interval with 2,000 resamples and a seed derived from `label`, so results are reproducible. Fewer than two values give `(NaN, NaN)`.

## Multiple comparisons

When you compare many models, `holm(pvalues)` applies the Holm–Bonferroni step-down correction.

## Agreement

`cohen_kappa(a, b)` measures chance-corrected agreement between two label sequences:

```text
κ = (p_o − p_e) / (1 − p_e)
```

> [!IMPORTANT]
> Kappa is agreement, not accuracy. Two models can agree and both be wrong. Runport reports it only as agreement.

## The CLI's heuristic scores

The `runport benchmark` command uses a simpler token-overlap heuristic for its accuracy and groundedness columns. See [Understanding results](/understanding-results#how-the-cli-benchmark-scores-answers) for exactly how it works and its limits.

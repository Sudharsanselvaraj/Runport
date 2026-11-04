---
title: Latency
description: How Runport measures latency, computes percentiles and checks an SLA.
---

## How latency is measured

Each `TargetResult` carries `latency_ms`. Connectors measure wall-clock time around the request. When a target does not report latency, `GenericRunner` uses its own timing around `execute()`. Latency that was never measured stays `None`; it is never recorded as 0.

## Run summaries

- `GenericRunResult.mean_latency_ms` is the mean across a run's cases.
- `runport compare-runs` shows mean latency for two runs side by side; see [Comparing runs](/comparing-runs).
- The web dashboard shows latency percentiles per model; see [Dashboards](/dashboards).

## Percentiles

`runport.scorers.performance.compute_percentile(values, p)` computes a percentile by linear interpolation between ranks:

```text
rank = (p / 100) × (n − 1)
value = v[floor(rank)] × (1 − w) + v[ceil(rank)] × w,   w = rank − floor(rank)
```

It returns `None` for an empty list. `runport.scorers.stats.pct` gives the same result over a NumPy array and ignores `NaN` values.

## Checking an SLA

```python
from runport.scorers.performance import LatencyP95Scorer

result = LatencyP95Scorer(threshold_ms=800).evaluate_batch([120.0, 340.5, 910.2, 455.0])
print(result.score, result.passed)   # 841.92 False; p50, p90 and p99 are in result.details
```

Without `threshold_ms`, `passed` is `None`: there is no pass/fail without a target.

## Confidence intervals

For a mean latency with uncertainty, use `runport.scorers.stats.boot_ci`: a bootstrap 95% interval with 2,000 resamples and a fixed seed. See [Quality evaluation](/quality-metrics#bootstrap-intervals).

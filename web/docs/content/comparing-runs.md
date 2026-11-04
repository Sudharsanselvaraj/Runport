---
title: Comparing runs
description: Put two stored runs side by side from the CLI or the web dashboard.
---

```bash
uv run runport compare-runs RUN_A RUN_B
```

`RUN_A` is the baseline and `RUN_B` the comparison. Both must exist in the database; otherwise the command reports which one is missing.

## What is compared

| Metric | Shown as |
|---|---|
| Mean accuracy | Run A, Run B, delta (B − A) |
| Mean groundedness | Run A, Run B, delta |
| Overall score | Run A, Run B, delta |
| Mean latency | Run A, Run B, delta |
| Total run spend | Run A, Run B, delta |
| Completed cases | Run A, Run B, delta |

> [!IMPORTANT]
> Compare like with like. The score columns mean different things depending on how a run was produced (heuristic scores for CLI live runs, completion rates for `GenericRunner`, fixed values for CLI replay). See [Understanding results](/understanding-results). A difference between two runs is only meaningful if both used the same dataset and split; the plan fingerprint in each run's notes tells you whether they did.

## Comparing more carefully

For a decision between models, compute metrics against human-approved labels and report intervals:

- Wilson intervals for accuracy (`runport.scorers.stats.wilson`);
- bootstrap intervals for latency and cost (`boot_ci`);
- Holm–Bonferroni correction when comparing many candidates (`holm`).

See [Quality evaluation](/quality-metrics).

## In the dashboard

The web dashboard has a comparison view with latency percentiles, validity rates and cost per model; see [Dashboards](/dashboards).

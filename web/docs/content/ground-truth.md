---
title: Ground truth and annotation
description: How Runport represents human-approved ground truth, and what runport annotate does today.
---

Supervised metrics are only as good as the labels behind them, so Runport records who verified each expected answer and where it came from.

## Verification records

Every case has a `verification` block:

```json
"verification": {
  "status": "VERIFIED",
  "reference_source": "Infrastructure Engineering Manual 2026",
  "verifier": "System Reviewer",
  "notes": "Approved benchmark fixture"
}
```

- `status` is `UNVERIFIED` (default), `VERIFIED` or `DISPUTED`.
- A `VERIFIED` record must name a `reference_source`, or it fails validation.

## Reviewing a dataset

```bash
uv run runport annotate data/evaluation/synthetic_seed_eval.jsonl --reviewer "Your Name"
```

> [!NOTE]
> In this release `annotate` is read-only: it loads the dataset, validates it, and lists each case's verification status and reference citation (the first 10 in the table). It does not edit labels. Change labels in the JSONL file itself, then re-run `validate-dataset`.

## Agreement is not accuracy

Agreement between two models, or between a model and an unverified reference, is reported as agreement, for example Cohen's kappa. Accuracy, F1 and calibration are computed only against labels a human approved. See [Quality evaluation](/quality-metrics#agreement).

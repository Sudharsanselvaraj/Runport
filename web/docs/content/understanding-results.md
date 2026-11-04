---
title: Understanding results
description: What a run stores, what each case status means, and exactly how each score is computed.
---

## What a run stores

Every run writes one run record and one result per case to the SQLite database.

| Run field | Meaning |
|---|---|
| `run_id`, `timestamp`, `model_id`, `dataset_path` | Identity |
| `total_cases`, `completed_cases`, `failed_cases` | Outcome counts |
| `total_cost_usd`, `mean_latency_ms` | Spend and speed |
| `mean_accuracy`, `mean_groundedness`, `mean_overall_score` | Scores (see below) |
| `is_dry_run` | `1` for offline plans and replay |

Each case result stores the prompt, expected answer, generated output, latency, prompt and completion tokens, cost, the scores, and evaluator notes.

## Case statuses

| Status | Meaning |
|---|---|
| `success` | The target returned non-empty output |
| `invalid_output` | The target returned, but the output was empty or whitespace |
| `failed` | The target raised an error |
| `timeout` | The request timed out |
| `rate_limited` | The provider kept rate-limiting after bounded retries |
| `unauthorized` | The provider rejected the credentials |

Trace exports group these as `OK`, `INVALID_OUTPUT` and `ERROR`.

## How the CLI benchmark scores answers

`runport benchmark --live` scores each answer with a deterministic heuristic (`RUBRIC_HEURISTIC`) against the case's `expected_answer`:

- **accuracy**: the share of the expected answer's words (longer than two characters, punctuation removed) that appear in the output;
- **groundedness**: `(overlap + 2) / (expected words + 2)`, reduced by 0.4 if the output contains "hallucination" or "error";
- **format adherence**: 1.0, minus 0.3 for outputs shorter than 15 characters and 0.2 for outputs without closing punctuation (minimum 0.2);
- **overall score**: `0.50 × accuracy + 0.35 × groundedness + 0.15 × format`.

> [!WARNING]
> These are word-overlap heuristics, not a judgment of correctness. Use [Scorers](/scorers) for stricter evaluation.

When a case has **no** expected answer, or the expected answer has no word longer than two characters, accuracy, groundedness and the overall score are left **empty** (shown as `—`). Format adherence is still recorded. Means are taken over the scored cases only, and a mean over no scored cases is empty, never 0.

## GenericRunner runs

`GenericRunner` records whether each case completed (`completed_cases`, `failed_cases`, and `format_adherence` of 1.0 for valid output or 0.0 for empty output). It does not judge correctness, so its accuracy, groundedness and overall columns are left **empty**. Score correctness with a scorer over `case_results`; see [Creating benchmarks](/creating-benchmarks#4-score-the-outputs).

## Replay runs

Replay runs score recorded outputs with the same heuristic as live runs. Cases without a recording are counted as failed and left unscored. See [Executing benchmark runs](/executing-runs#replay-mode).

## Cost

Each result's cost has a provenance label; a `None` cost is unknown, not free. See [Cost analysis](/cost-analysis).

---
title: Scorers
description: The BaseScorer contract and every scorer that ships with Runport.
---

A scorer compares one prediction with one expectation and returns a `ScoreResult`. Scorers live in `runport.scorers` and are independent of how the output was produced, so they work on CLI results, `GenericRunner` case results or your own data.

> [!NOTE]
> `runport.scorers` needs the `report` or `dev` extra (numpy and pandas). See [Installation](/installation#install-with-uv).

## The contract

```python
from runport.scorers.base import BaseScorer, ScoreResult

class MyScorer(BaseScorer):
    def __init__(self):
        super().__init__(name="my_metric")

    def score(self, predicted, expected, context=None) -> ScoreResult:
        if predicted is None or expected is None:
            return ScoreResult(metric_name=self.name, score=None, details={"reason": "missing input"})
        ok = str(predicted).strip() == str(expected).strip()
        return ScoreResult(metric_name=self.name, score=1.0 if ok else 0.0, passed=ok)
```

| `ScoreResult` field | Type | Meaning |
|---|---|---|
| `metric_name` | `str` | The scorer's name |
| `score` | `float` or `None` | `None` when there was nothing to score, never `0` |
| `passed` | `bool` or `None` | Pass/fail when the scorer defines one |
| `details` | `dict` | Scorer-specific breakdown |

## Built-in scorers

| Scorer | Module | Measures |
|---|---|---|
| `ExactMatchScorer` | `match` | Exact equality, optionally case- and whitespace-insensitive |
| `RegexMatchScorer` | `match` | Output matches (or contains, with `search_mode=True`) a regex |
| `AccuracyScorer` | `classification` | Exact-match label accuracy |
| `ClassificationReportScorer` | `classification` | Precision, recall, F1 per class and a confusion matrix |
| `BrierScoreScorer` | `classification` | Brier score of a binary probability |
| `JSONSchemaScorer` | `extraction` | Output parses as a JSON object with the required keys |
| `FieldMatchScorer` | `extraction` | Field-level precision, recall and F1 |
| `KeywordContainmentScorer` | `generation` | Share of expected keywords or claims present |
| `TokenOverlapScorer` | `generation` | Token precision, recall and F1 (ROUGE-1 style) |
| `LLMJudgeScorer` | `llm_judge` | A 1–5 rubric score from a judge function you supply |
| `LatencyP95Scorer` | `performance` | p95 latency against an optional SLA |
| `CostPer1kScorer` | `performance` | Projected cost per 1,000 cases against an optional ceiling |

See [Classification](/classification), [Generation](/generation) and [Extraction](/extraction) for details, and [Plugins](/plugins) to ship your own scorer as a package.

## LLM-as-a-judge

`LLMJudgeScorer` formats a rubric (groundedness, accuracy, completeness) and passes it to a `judge_fn(prompt) -> str` that you provide; it parses a JSON verdict with `score` (1–5), `grounded` and `reasoning`. Runport never calls a judge model on its own, and tests use deterministic local judge functions.

> [!IMPORTANT]
> A judge's score is a model's opinion. Report it as such, alongside, not instead of, metrics computed against human-approved ground truth. See [Invariants](/invariants#8-agreement-is-not-correctness).

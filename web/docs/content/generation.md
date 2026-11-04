---
title: Generation
description: Score open-ended answers with keyword containment and token overlap.
---

Generation scorers live in `runport.scorers.generation`. Both are deterministic and run offline.

## Keyword containment

`KeywordContainmentScorer` checks how many expected keywords or claims appear in the response (case-insensitive).

```python
from runport.scorers.generation import KeywordContainmentScorer

scorer = KeywordContainmentScorer()
r = scorer.score(
    "Each container supports up to 64 GB of RAM.",
    expected=None,
    context={"keywords": ["64 GB", "RAM"]},
)
print(r.score, r.passed)   # 1.0 True
```

Keywords come from `context["keywords"]` or `context["expected_claims"]`, or from `expected` when it is a list. The score is the share found; `passed` is true only when all are present. With no keywords, the score is `None`.

The dataset field `expected_claims` is designed for this scorer; see [Datasets](/datasets#the-case-schema).

## Token overlap

`TokenOverlapScorer` computes token-level precision, recall and F1 between the response and a reference answer, in the style of ROUGE-1.

```python
from runport.scorers.generation import TokenOverlapScorer

r = TokenOverlapScorer().score("Paris is the capital", "The capital is Paris")
print(r.score, r.details)   # f1 with precision and recall
```

`passed` is true at F1 ≥ 0.8. A missing prediction or reference gives `None`.

> [!NOTE]
> Overlap measures wording, not truth. Use it for regression checks between versions, and verify factual answers against human-approved references.

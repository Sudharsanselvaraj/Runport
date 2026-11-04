---
title: Extraction
description: Score structured output: JSON validity, required keys and field-level F1.
---

Extraction scorers live in `runport.scorers.extraction`.

## JSON validity and required keys

`JSONSchemaScorer(required_keys=[...])` passes when the output parses as a JSON object containing every required key. A surrounding Markdown code fence (` ```json `) is stripped first.

```python
from runport.scorers.extraction import JSONSchemaScorer

r = JSONSchemaScorer(required_keys=["name", "date"]).score('{"name": "A", "date": "2026-01-01"}', None)
print(r.score, r.passed)   # 1.0 True
```

| Outcome | `score` |
|---|---|
| Valid object with all required keys | `1.0` |
| Not JSON, not an object, or keys missing | `0.0` |
| No prediction | `None` |

## Field-level F1

`FieldMatchScorer` compares predicted and expected key-value pairs (dicts or JSON strings). A field is a true positive when the key exists and the values match after trimming.

```python
from runport.scorers.extraction import FieldMatchScorer

r = FieldMatchScorer().score({"name": "A", "city": "Rome"}, {"name": "A", "city": "Milan"})
print(r.score, r.details)   # 0.667: precision 0.5, recall 1.0 (tp 1, fp 1, fn 0)
```

`passed` is true only at F1 = 1.0.

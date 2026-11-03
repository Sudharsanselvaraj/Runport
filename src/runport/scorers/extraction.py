"""Scorers for structured data and entity extraction workloads."""

import json
from typing import Any, Dict, List, Optional, Set

from runport.scorers.base import BaseScorer, ScoreResult
from runport.scorers.stats import prf


class JSONSchemaScorer(BaseScorer):
    """Evaluates whether model output parses as valid JSON adhering to required keys."""

    def __init__(self, required_keys: Optional[List[str]] = None, name: str = "json_validity"):
        super().__init__(name=name)
        self.required_keys = set(required_keys or [])

    def score(
        self,
        predicted: Any,
        expected: Any,
        context: Optional[Dict[str, Any]] = None,
    ) -> ScoreResult:
        if predicted is None:
            return ScoreResult(metric_name=self.name, score=None, passed=False, details={"reason": "Null prediction"})

        text = str(predicted).strip()
        # Clean markdown codeblocks if present
        if text.startswith("```json"):
            text = text[7:]
        if text.startswith("```"):
            text = text[3:]
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()

        try:
            data = json.loads(text)
        except Exception as e:
            return ScoreResult(metric_name=self.name, score=0.0, passed=False, details={"error": str(e)})

        if not isinstance(data, dict):
            return ScoreResult(metric_name=self.name, score=0.0, passed=False, details={"error": "Output is not a JSON object"})

        missing = self.required_keys - set(data.keys())
        if missing:
            return ScoreResult(
                metric_name=self.name,
                score=0.5,
                passed=False,
                details={"missing_keys": list(missing)},
            )

        return ScoreResult(metric_name=self.name, score=1.0, passed=True, details={"keys_present": list(data.keys())})


class FieldMatchScorer(BaseScorer):
    """Calculates field-level precision, recall, and F1 across extracted key-value pairs."""

    def __init__(self, name: str = "field_f1"):
        super().__init__(name=name)

    def score(
        self,
        predicted: Any,
        expected: Any,
        context: Optional[Dict[str, Any]] = None,
    ) -> ScoreResult:
        if predicted is None or expected is None:
            return ScoreResult(metric_name=self.name, score=None, details={"reason": "Missing prediction or ground truth"})

        pred_dict = self._to_dict(predicted)
        exp_dict = self._to_dict(expected)

        if pred_dict is None or exp_dict is None:
            return ScoreResult(metric_name=self.name, score=0.0, passed=False, details={"error": "Failed to parse dictionary"})

        all_keys = set(exp_dict.keys())
        tp = sum(1 for k in all_keys if k in pred_dict and str(pred_dict[k]).strip() == str(exp_dict[k]).strip())
        fp = sum(1 for k in pred_dict if k not in exp_dict or str(pred_dict[k]).strip() != str(exp_dict.get(k, "")).strip())
        fn = sum(1 for k in all_keys if k not in pred_dict)

        p, r, f1 = prf(tp, fp, fn)
        return ScoreResult(
            metric_name=self.name,
            score=f1 if f1 == f1 else 0.0,
            passed=(f1 == 1.0),
            details={"precision": p, "recall": r, "f1": f1, "tp": tp, "fp": fp, "fn": fn},
        )

    def _to_dict(self, val: Any) -> Optional[Dict[str, Any]]:
        if isinstance(val, dict):
            return val
        if isinstance(val, str):
            try:
                data = json.loads(val.strip())
                if isinstance(data, dict):
                    return data
            except Exception:
                pass
        return None


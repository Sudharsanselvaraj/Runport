"""Statistical classification metrics and calibration scorers."""

from typing import Any, Dict, List, Optional
import math

from runport.scorers.base import BaseScorer, ScoreResult
from runport.scorers.stats import prf, wilson


class AccuracyScorer(BaseScorer):
    """Computes exact match binary accuracy for classification."""

    def __init__(self, name: str = "accuracy"):
        super().__init__(name=name)

    def score(
        self,
        predicted: Any,
        expected: Any,
        context: Optional[Dict[str, Any]] = None,
    ) -> ScoreResult:
        if predicted is None or expected is None:
            return ScoreResult(metric_name=self.name, score=None, passed=None, details={"reason": "Missing prediction or ground truth"})

        pred_str = str(predicted).strip().upper()
        exp_str = str(expected).strip().upper()
        match = (pred_str == exp_str)
        return ScoreResult(
            metric_name=self.name,
            score=1.0 if match else 0.0,
            passed=match,
            details={"predicted": pred_str, "expected": exp_str},
        )


class BrierScoreScorer(BaseScorer):
    """Computes Brier score for probabilistic binary classification.
    
    (probability - outcome)^2
    """

    def __init__(self, name: str = "brier_score"):
        super().__init__(name=name)

    def score(
        self,
        predicted: Any,
        expected: Any,
        context: Optional[Dict[str, Any]] = None,
    ) -> ScoreResult:
        ctx = context or {}
        prob = ctx.get("probability")
        if prob is None or expected is None:
            return ScoreResult(metric_name=self.name, score=None, details={"reason": "Missing probability"})

        try:
            p = float(prob)
            y = 1.0 if bool(expected) else 0.0
            brier = (p - y) ** 2
            return ScoreResult(
                metric_name=self.name,
                score=brier,
                details={"probability": p, "outcome": y},
            )
        except (ValueError, TypeError):
            return ScoreResult(metric_name=self.name, score=None, details={"reason": "Invalid probability format"})

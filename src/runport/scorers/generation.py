"""Scorers for generation, summarization, and open-ended text quality."""

import re
from typing import Any, Dict, List, Optional, Set

from runport.scorers.base import BaseScorer, ScoreResult
from runport.scorers.stats import prf


class KeywordContainmentScorer(BaseScorer):
    """Checks whether expected key claims or keywords are present in the response."""

    def __init__(self, name: str = "keyword_containment"):
        super().__init__(name=name)

    def score(
        self,
        predicted: Any,
        expected: Any,
        context: Optional[Dict[str, Any]] = None,
    ) -> ScoreResult:
        if predicted is None:
            return ScoreResult(metric_name=self.name, score=None, passed=False, details={"reason": "Null prediction"})

        ctx = context or {}
        keywords = ctx.get("keywords") or ctx.get("expected_claims")
        if not keywords:
            if isinstance(expected, list):
                keywords = expected
            elif isinstance(expected, str):
                keywords = [expected]
            else:
                return ScoreResult(metric_name=self.name, score=None, details={"reason": "No keywords specified"})

        text = str(predicted).lower()
        matched = [k for k in keywords if str(k).lower() in text]
        score = len(matched) / len(keywords) if keywords else 1.0

        return ScoreResult(
            metric_name=self.name,
            score=score,
            passed=(score == 1.0),
            details={"matched_keywords": matched, "total_keywords": len(keywords)},
        )


class TokenOverlapScorer(BaseScorer):
    """Computes token-level precision, recall, and F1 (ROUGE-1 equivalent)."""

    def __init__(self, name: str = "token_overlap"):
        super().__init__(name=name)

    def _tokenize(self, text: str) -> List[str]:
        return re.findall(r"\w+", text.lower())

    def score(
        self,
        predicted: Any,
        expected: Any,
        context: Optional[Dict[str, Any]] = None,
    ) -> ScoreResult:
        if predicted is None or expected is None:
            return ScoreResult(metric_name=self.name, score=None, details={"reason": "Missing prediction or reference"})

        pred_tokens = self._tokenize(str(predicted))
        exp_tokens = self._tokenize(str(expected))

        if not pred_tokens or not exp_tokens:
            return ScoreResult(metric_name=self.name, score=0.0, passed=False, details={"pred_tokens": 0, "exp_tokens": 0})

        pred_counts: Dict[str, int] = {}
        for t in pred_tokens:
            pred_counts[t] = pred_counts.get(t, 0) + 1

        exp_counts: Dict[str, int] = {}
        for t in exp_tokens:
            exp_counts[t] = exp_counts.get(t, 0) + 1

        common = 0
        for t, c in pred_counts.items():
            if t in exp_counts:
                common += min(c, exp_counts[t])

        p, r, f1 = prf(common, len(pred_tokens) - common, len(exp_tokens) - common)
        return ScoreResult(
            metric_name=self.name,
            score=f1 if f1 == f1 else 0.0,
            passed=(f1 >= 0.8),
            details={"precision": p, "recall": r, "f1": f1},
        )


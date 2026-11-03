"""Exact and regex matching scorers for Runport benchmarks.

Invariant 1: Null is not 0. Missing predictions or references return None.
"""

import re
from typing import Any, Dict, Optional

from runport.scorers.base import BaseScorer, ScoreResult


class ExactMatchScorer(BaseScorer):
    """Scorer for exact or whitespace/case-normalized text matching."""

    def __init__(
        self,
        name: str = "exact_match",
        ignore_case: bool = False,
        normalize_whitespace: bool = False,
    ):
        super().__init__(name=name)
        self.ignore_case = ignore_case
        self.normalize_whitespace = normalize_whitespace

    def _normalize(self, text: str) -> str:
        res = str(text)
        if self.normalize_whitespace:
            res = " ".join(res.split())
        else:
            res = res.strip()
        if self.ignore_case:
            res = res.lower()
        return res

    def score(
        self,
        predicted: Any,
        expected: Any,
        context: Optional[Dict[str, Any]] = None,
    ) -> ScoreResult:
        if predicted is None or expected is None:
            return ScoreResult(
                metric_name=self.name,
                score=None,
                passed=None,
                details={"reason": "Missing predicted or expected value"},
            )

        norm_pred = self._normalize(predicted)
        norm_exp = self._normalize(expected)
        is_match = (norm_pred == norm_exp)

        return ScoreResult(
            metric_name=self.name,
            score=1.0 if is_match else 0.0,
            passed=is_match,
            details={
                "predicted": norm_pred,
                "expected": norm_exp,
                "ignore_case": self.ignore_case,
                "normalize_whitespace": self.normalize_whitespace,
            },
        )


class RegexMatchScorer(BaseScorer):
    """Scorer verifying that candidate output matches an expected regular expression."""

    def __init__(
        self,
        pattern: str,
        name: str = "regex_match",
        flags: int = 0,
        search_mode: bool = False,
    ):
        super().__init__(name=name)
        self.pattern = pattern
        self.flags = flags
        self.search_mode = search_mode
        self._compiled = re.compile(pattern, flags)

    def score(
        self,
        predicted: Any,
        expected: Any = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> ScoreResult:
        if predicted is None:
            return ScoreResult(
                metric_name=self.name,
                score=None,
                passed=None,
                details={"reason": "Missing prediction"},
            )

        text = str(predicted)
        if self.search_mode:
            matched = bool(self._compiled.search(text))
        else:
            matched = bool(self._compiled.fullmatch(text.strip()))

        return ScoreResult(
            metric_name=self.name,
            score=1.0 if matched else 0.0,
            passed=matched,
            details={
                "pattern": self.pattern,
                "search_mode": self.search_mode,
                "matched": matched,
            },
        )


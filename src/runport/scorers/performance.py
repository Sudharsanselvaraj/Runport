"""Performance, latency distribution, and unit economics scorers.

Invariant 1: Null is not 0. Missing cost or latency returns None.
"""

from decimal import Decimal
import math
from typing import Any, Dict, List, Optional, Sequence

from runport.scorers.base import BaseScorer, ScoreResult


def compute_percentile(values: Sequence[float], percentile: float) -> Optional[float]:
    """Computes an exact percentile from a sequence of numeric measurements."""
    if not values:
        return None
    sorted_vals = sorted(values)
    n = len(sorted_vals)
    if n == 1:
        return sorted_vals[0]
    rank = (percentile / 100.0) * (n - 1)
    lower = int(math.floor(rank))
    upper = int(math.ceil(rank))
    weight = rank - lower
    return sorted_vals[lower] * (1.0 - weight) + sorted_vals[upper] * weight


class LatencyP95Scorer(BaseScorer):
    """Evaluates 95th percentile latency against an SLA ceiling in milliseconds."""

    def __init__(self, threshold_ms: Optional[float] = None, name: str = "latency_p95"):
        super().__init__(name=name)
        self.threshold_ms = threshold_ms

    def evaluate_batch(self, latencies_ms: Sequence[float]) -> ScoreResult:
        """Computes p95 latency and validates against threshold."""
        valid_lats = [float(l) for l in latencies_ms if l is not None and not math.isnan(l)]
        if not valid_lats:
            return ScoreResult(
                metric_name=self.name,
                score=None,
                passed=None,
                details={"reason": "No valid latency observations provided"},
            )

        p95 = round(compute_percentile(valid_lats, 95.0), 2)
        passed = (p95 <= self.threshold_ms) if self.threshold_ms is not None else None

        return ScoreResult(
            metric_name=self.name,
            score=p95,
            passed=passed,
            details={
                "n_samples": len(valid_lats),
                "threshold_ms": self.threshold_ms,
                "p50_ms": round(compute_percentile(valid_lats, 50.0), 2),
                "p90_ms": round(compute_percentile(valid_lats, 90.0), 2),
                "p99_ms": round(compute_percentile(valid_lats, 99.0), 2),
            },
        )

    def score(
        self,
        predicted: Any,
        expected: Any = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> ScoreResult:
        ctx = context or {}
        lats = ctx.get("latencies_ms")
        if lats is not None:
            return self.evaluate_batch(lats)
        lat = ctx.get("latency_ms") or predicted
        if lat is None:
            return ScoreResult(metric_name=self.name, score=None, details={"reason": "Missing latency"})
        return self.evaluate_batch([float(lat)])


class CostPer1kScorer(BaseScorer):
    """Computes projected cost per 1,000 cases and checks against spend ceilings."""

    def __init__(
        self,
        max_cost_per_1k_usd: Optional[Decimal] = None,
        name: str = "cost_per_1k",
    ):
        super().__init__(name=name)
        self.max_cost_per_1k_usd = max_cost_per_1k_usd

    def evaluate(self, total_cost_usd: Optional[Decimal], case_count: int) -> ScoreResult:
        """Computes cost per 1,000 cases."""
        if total_cost_usd is None or case_count <= 0:
            return ScoreResult(
                metric_name=self.name,
                score=None,
                passed=None,
                details={"reason": "Missing cost or zero case count"},
            )

        cost_per_case = total_cost_usd / Decimal(case_count)
        cost_per_1k = cost_per_case * Decimal("1000")
        cost_float = float(round(cost_per_1k, 6))

        passed = None
        if self.max_cost_per_1k_usd is not None:
            passed = cost_per_1k <= self.max_cost_per_1k_usd

        return ScoreResult(
            metric_name=self.name,
            score=cost_float,
            passed=passed,
            details={
                "total_cost_usd": str(total_cost_usd),
                "case_count": case_count,
                "cost_per_case_usd": str(cost_per_case),
                "cost_per_1k_usd": str(cost_per_1k),
                "max_cost_per_1k_usd": str(self.max_cost_per_1k_usd) if self.max_cost_per_1k_usd else None,
            },
        )

    def score(
        self,
        predicted: Any,
        expected: Any = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> ScoreResult:
        ctx = context or {}
        cost = ctx.get("total_cost_usd")
        count = ctx.get("case_count", 1)
        if cost is None:
            return ScoreResult(metric_name=self.name, score=None, details={"reason": "Missing cost"})
        return self.evaluate(Decimal(str(cost)), count)


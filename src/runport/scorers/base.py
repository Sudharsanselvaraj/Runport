"""Base scorer abstraction for Runport evaluations.

Invariant 1: Null is not 0. Missing scores or values remain None,
never fabricated or defaulted to zero.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, Optional


@dataclass(frozen=True)
class ScoreResult:
    """Standard outcome of a scoring evaluation."""

    metric_name: str
    score: Optional[float]
    passed: Optional[bool] = None
    details: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        # Enforce that score is a float or None
        if self.score is not None:
            object.__setattr__(self, "score", float(self.score))


class BaseScorer(ABC):
    """Abstract base class for all metric scorers."""

    def __init__(self, name: str):
        self.name = name

    @abstractmethod
    def score(
        self,
        predicted: Any,
        expected: Any,
        context: Optional[Dict[str, Any]] = None,
    ) -> ScoreResult:
        """Evaluate a predicted output against ground truth expectations."""
        pass

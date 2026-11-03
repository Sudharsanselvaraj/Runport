"""Base workload definition for Runport evaluation scenarios."""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from runport.scorers.base import BaseScorer


class BaseWorkload(ABC):
    """Abstract specification for an evaluation task or domain workload."""

    def __init__(self, name: str, description: str = ""):
        self.name = name
        self.description = description

    @abstractmethod
    def prepare_prompt(self, case: Dict[str, Any]) -> str:
        """Transform an evaluation case dictionary into a standardized prompt string."""
        pass

    @abstractmethod
    def validate_output(self, raw_output: Any) -> bool:
        """Check whether the raw output satisfies workload format invariants."""
        pass

    @abstractmethod
    def get_scorers(self) -> List[BaseScorer]:
        """Return the default scorers associated with this workload."""
        pass


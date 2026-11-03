"""Classification workload specification."""

from typing import Any, Dict, List, Optional, Sequence

from runport.scorers.base import BaseScorer
from runport.scorers.classification import AccuracyScorer, BrierScoreScorer
from runport.workloads.base import BaseWorkload


class ClassificationWorkload(BaseWorkload):
    """Workload for single-label or multi-class categorical and sentiment classification."""

    def __init__(
        self,
        name: str = "classification",
        allowed_labels: Optional[Sequence[str]] = None,
        prompt_template: str = "Classify the following text into one of {labels}:\n\nText: {input}\n\nCategory:",
    ):
        super().__init__(name=name, description="Classification task evaluating categorical label predictions.")
        self.allowed_labels = [l.upper() for l in (allowed_labels or ["YES", "NO"])]
        self.prompt_template = prompt_template

    def prepare_prompt(self, case: Dict[str, Any]) -> str:
        text = str(case.get("input") or case.get("query") or case.get("text") or "")
        return self.prompt_template.format(labels=", ".join(self.allowed_labels), input=text)

    def validate_output(self, raw_output: Any) -> bool:
        if raw_output is None:
            return False
        cleaned = str(raw_output).strip().upper()
        if not self.allowed_labels:
            return bool(cleaned)
        return any(cleaned == l or cleaned.startswith(l) for l in self.allowed_labels)

    def get_scorers(self) -> List[BaseScorer]:
        return [AccuracyScorer(), BrierScoreScorer()]

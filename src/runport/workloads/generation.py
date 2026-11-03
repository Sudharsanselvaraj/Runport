"""Free-form generation, dialogue, and summarization workload."""

from typing import Any, Dict, List, Optional

from runport.scorers.base import BaseScorer
from runport.scorers.generation import KeywordContainmentScorer, TokenOverlapScorer
from runport.workloads.base import BaseWorkload


class GenerationWorkload(BaseWorkload):
    """Workload evaluating open-ended text synthesis, summarization, and query responses."""

    def __init__(
        self,
        name: str = "generation",
        prompt_template: str = "{instruction}\n\nInput: {input}\n\nResponse:",
    ):
        super().__init__(name=name, description="Generation workload evaluating open-ended answer quality and keyword recall.")
        self.prompt_template = prompt_template

    def prepare_prompt(self, case: Dict[str, Any]) -> str:
        instruction = str(case.get("instruction") or "Answer the following question clearly and concisely:")
        inp = str(case.get("input") or case.get("query") or "")
        return self.prompt_template.format(instruction=instruction, input=inp)

    def validate_output(self, raw_output: Any) -> bool:
        if raw_output is None:
            return False
        return len(str(raw_output).strip()) > 0

    def get_scorers(self) -> List[BaseScorer]:
        return [TokenOverlapScorer(), KeywordContainmentScorer()]


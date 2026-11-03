"""Retrieval-Augmented Generation (RAG) workload."""

from typing import Any, Dict, List, Optional

from runport.scorers.base import BaseScorer
from runport.scorers.generation import KeywordContainmentScorer, TokenOverlapScorer
from runport.workloads.base import BaseWorkload


class RAGWorkload(BaseWorkload):
    """Workload evaluating grounded answer generation given retrieved contexts."""

    def __init__(
        self,
        name: str = "rag",
        prompt_template: str = "Context:\n{context}\n\nQuestion: {query}\n\nAnswer based strictly on the context above:",
    ):
        super().__init__(name=name, description="RAG workload evaluating answer correctness, context groundedness, and abstention.")
        self.prompt_template = prompt_template

    def prepare_prompt(self, case: Dict[str, Any]) -> str:
        ctx = str(case.get("context") or case.get("retrieved_context") or "")
        q = str(case.get("query") or case.get("input") or "")
        return self.prompt_template.format(context=ctx, query=q)

    def validate_output(self, raw_output: Any) -> bool:
        if raw_output is None:
            return False
        return len(str(raw_output).strip()) > 0

    def get_scorers(self) -> List[BaseScorer]:
        return [TokenOverlapScorer(), KeywordContainmentScorer()]

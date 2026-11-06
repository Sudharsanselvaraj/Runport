"""A RAG pipeline (retriever + OpenRouter generation) as a Target, so it runs through GenericRunner."""

from __future__ import annotations

import inspect
from typing import Any, Dict, Optional

from runport.connectors.openrouter import OpenRouterTarget
from runport.providers.base import BaseProvider
from runport.rag.evaluator import RAGSystemEvaluator
from runport.rag.retriever import BaseRetriever
from runport.schemas.evaluation import EvaluationCase
from runport.targets.base import TargetResult, TargetStatus

RAG_SYSTEM_PROMPT = (
    "You are an AI assistant and knowledge retrieval agent. "
    "Answer the student's question accurately, grounded strictly in the provided Context. "
    "Never invent fees or qualification criteria. If the context does not contain sufficient details, state that clearly."
)


class RagPipelineTarget(OpenRouterTarget):
    """Retrieves context for the case, then generates a grounded answer.

    The retrieval pass is local (no spend). The generation pass is a billable OpenRouter request with the same cost
    provenance as OpenRouterTarget. ``latency_ms`` is retrieval + generation; both parts are kept in metadata.
    """

    def __init__(self, model_id: str, retriever: BaseRetriever, adapter: Optional[BaseProvider] = None, top_k: int = 2) -> None:
        super().__init__(model_id=model_id, adapter=adapter, system_prompt=None)  # type: ignore[arg-type]
        self.retriever = retriever
        self.top_k = top_k
        self.capabilities = ["text", "usage", "cost", "retrieval"]

    def execute(self, input_payload: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> TargetResult:
        case = EvaluationCase.model_validate(input_payload)
        if "top_k" in inspect.signature(self.retriever.retrieve).parameters:
            ret = self.retriever.retrieve(case, top_k=self.top_k)  # type: ignore[call-arg]
        else:
            ret = self.retriever.retrieve(case)
        context_block = "\n---\n".join(ret.chunks) if ret.chunks else "NO_CONTEXT_RETRIEVED"
        messages = [
            {"role": "system", "content": RAG_SYSTEM_PROMPT},
            {"role": "user", "content": f"Context:\n{context_block}\n\nStudent Query: {case.query}"},
        ]
        res = self.generate_messages(messages, case_id=case.id)
        res.metadata["retrieval"] = {
            "retriever_id": ret.retriever_id,
            "chunks": list(ret.chunks),
            "record_ids": list(ret.retrieved_record_ids),
            "hit_rate": ret.hit_rate,
            "precision": ret.precision,
            "latency_ms": ret.latency_ms,
        }
        res.metadata["generation_latency_ms"] = res.latency_ms
        if res.latency_ms is not None:
            res.latency_ms = round(ret.latency_ms + res.latency_ms, 2)
        return res


def rag_case_scorer(case: Dict[str, Any], result: TargetResult) -> Dict[str, Any]:
    """Answer correctness and groundedness against the retrieved context, persisted with each case."""
    if result.status != TargetStatus.SUCCESS:
        return {}
    chunks = (result.metadata.get("retrieval") or {}).get("chunks") or []
    ans, grd = RAGSystemEvaluator().evaluate_generation(
        generated_output=result.output_text or "", retrieved_chunks=chunks, expected_answer=case.get("expected_answer")
    )
    # Without a reference answer there is no correctness, so there is no overall score either (null is not 0).
    return {"accuracy": ans, "groundedness": grd, "overall_score": round((ans + grd) / 2.0, 4) if ans is not None else None}

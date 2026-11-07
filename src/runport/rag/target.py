"""A RAG pipeline (retriever + OpenRouter generation) as a Target, so it runs through GenericRunner."""

from __future__ import annotations

import inspect
import uuid
from typing import Any, Dict, Optional

from runport.connectors.openrouter import OpenRouterTarget
from runport.providers.base import BaseProvider, scrub_secrets
from runport.rag.evaluator import RAGSystemEvaluator
from runport.rag.retriever import BaseRetriever
from runport.schemas.evaluation import EvaluationCase
from runport.targets.base import TargetResult, TargetStatus
from runport.traces.domain import Span, SpanKind, SpanStatus

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

        retrieval_span = Span(
            trace_id="pending",
            span_id=f"sp-retrieval-{uuid.uuid4().hex[:10]}",
            parent_span_id=None,
            name=f"retrieval:{ret.retriever_id}",
            kind=SpanKind.RETRIEVAL,
            status=SpanStatus.OK,
            duration_ms=round(ret.latency_ms, 3) if ret.latency_ms is not None else None,
            attributes=scrub_secrets({
                "retriever_id": ret.retriever_id,
                "top_k": self.top_k,
                "chunks_count": len(ret.chunks),
                "record_ids": list(ret.retrieved_record_ids),
                "hit_rate": ret.hit_rate,
                "precision": ret.precision,
            }),
        )

        gen_lat = res.metadata.get("generation_latency_ms")
        tot_tokens = (
            res.tokens_in + res.tokens_out
        ) if (res.tokens_in is not None and res.tokens_out is not None) else None

        generation_span = Span(
            trace_id="pending",
            span_id=f"sp-llm-{uuid.uuid4().hex[:10]}",
            parent_span_id=None,
            name=f"llm:{self.model_id}",
            kind=SpanKind.LLM,
            status=SpanStatus.OK if res.status == TargetStatus.SUCCESS else SpanStatus.ERROR,
            duration_ms=round(gen_lat, 3) if gen_lat is not None else None,
            model=self.model_id,
            prompt_tokens=res.tokens_in,
            completion_tokens=res.tokens_out,
            total_tokens=tot_tokens,
            cost_usd=f"{res.cost_usd:.6f}" if res.cost_usd is not None else None,
            cost_basis=res.cost_basis.value if res.cost_basis else None,
            attributes=scrub_secrets({"model_id": self.model_id}),
            error=scrub_secrets(res.error_message) if res.status != TargetStatus.SUCCESS else None,
        )

        res.trajectory = [retrieval_span, generation_span]
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
    return {
        "accuracy": ans,
        "groundedness": grd,
        "overall_score": round((ans + grd) / 2.0, 4) if ans is not None else None,
        "kind": "heuristic",  # lexical overlap, not supervised accuracy
        "evaluator": "rag_overlap_v1",
    }

"""Evaluator for decoupled RAG metrics: retrieval precision, answer correctness, groundedness, and failure attribution."""

import re
from typing import List, Optional, Set, Tuple


class RAGSystemEvaluator:
    """Evaluates RAG outputs across decoupled retrieval and generation axes."""

    @staticmethod
    def _tokenize(text: str) -> Set[str]:
        cleaned = re.sub(r"[^\w\s]", "", text.lower())
        return set(w for w in cleaned.split() if len(w) > 2)

    def evaluate_generation(
        self,
        generated_output: str,
        retrieved_chunks: List[str],
        expected_answer: Optional[str] = None,
    ) -> Tuple[Optional[float], float]:
        """Calculates answer correctness and faithfulness (groundedness).

        Returns:
            (answer_correctness, groundedness)
            answer_correctness is None if expected_answer is not provided (Null is not 0 / no guessing).
        """
        out_clean = generated_output.strip()
        if not out_clean:
            return 0.0, 0.0

        gen_tokens = self._tokenize(out_clean)
        if not gen_tokens:
            return 0.0, 0.0

        # 1. Answer Correctness (overlap with ground truth; None if no ground truth provided)
        if expected_answer and expected_answer.strip():
            ref_tokens = self._tokenize(expected_answer)
            overlap = len(ref_tokens.intersection(gen_tokens))
            correctness: Optional[float] = round(min(1.0, overlap / len(ref_tokens)), 4) if ref_tokens else None
        else:
            correctness = None

        # 2. Groundedness (faithfulness against retrieved context)
        context_str = " ".join(retrieved_chunks)
        if context_str.strip():
            ctx_tokens = self._tokenize(context_str)
            supported = len(gen_tokens.intersection(ctx_tokens))
            groundedness = min(1.0, (supported + 2) / (len(gen_tokens) + 2))

            # Detect ungrounded RM tuition fees (strict hallucination check)
            out_fees = re.findall(r"rm\s*[\d,]+", out_clean.lower())
            ctx_fees = re.findall(r"rm\s*[\d,]+", context_str.lower())
            for fee in out_fees:
                if fee not in ctx_fees:
                    groundedness = max(0.0, groundedness - 0.35)
        else:
            # When retrieval is completely empty, any output claiming facts is ungrounded
            groundedness = 0.20 if len(out_clean) > 20 else 0.80

        return correctness, round(groundedness, 4)

    def attribute_failure(
        self,
        retrieval_hit_rate: float,
        answer_correctness: Optional[float],
        groundedness: float,
    ) -> str:
        """Categorizes whether failure originated in the retriever, generator, or both."""
        ret_ok = retrieval_hit_rate >= 0.50
        gen_ok = (answer_correctness >= 0.60 if answer_correctness is not None else False) and groundedness >= 0.50

        if ret_ok and gen_ok:
            return "SYSTEM_SUCCESS"
        elif not ret_ok and not gen_ok:
            return "RETRIEVAL_FAILURE"
        elif ret_ok and not gen_ok:
            return "GENERATION_FAILURE"
        else:
            return "PARAMETRIC_MEMORY_RESCUE"

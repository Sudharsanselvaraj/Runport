"""Rubric-based evaluation scoring for model outputs against verified ground truths."""

import re
from typing import Optional, Set
from runport.schemas.scoring import EvaluationScore


class RubricEvaluator:
    """Evaluates factual accuracy, groundedness, and format adherence."""

    @staticmethod
    def _tokenize(text: str) -> Set[str]:
        """Extracts normalized words for lexical overlap."""
        cleaned = re.sub(r"[^\w\s]", "", text.lower())
        return set(w for w in cleaned.split() if len(w) > 2)

    def evaluate(
        self,
        score_id: str,
        execution_id: str,
        generated_output: str,
        expected_answer: Optional[str] = None,
    ) -> EvaluationScore:
        """Computes deterministic rubric scores."""
        out_clean = generated_output.strip()

        # 1. Format adherence: non-empty, proper punctuation, reasonable length
        has_reference = bool(expected_answer and expected_answer.strip())
        if not out_clean:
            # An empty answer to a labelled case is wrong (0). Without a label there is nothing to score.
            return EvaluationScore(
                score_id=score_id,
                execution_id=execution_id,
                accuracy=0.0 if has_reference else None,
                groundedness=0.0 if has_reference else None,
                format_adherence=0.0,
                evaluator_type="RUBRIC_HEURISTIC",
                notes="Generated response was empty.",
            )

        format_adherence = 1.0
        if len(out_clean) < 15:
            format_adherence -= 0.3
        if not out_clean.endswith((".", "!", "?")):
            format_adherence -= 0.2
        format_adherence = max(0.2, min(1.0, format_adherence))

        # 2. Accuracy & Groundedness (lexical overlap with the reference; unmeasured stays None)
        accuracy: Optional[float] = None
        groundedness: Optional[float] = None
        notes = "Rubric heuristic: word overlap with the verified reference answer."
        if has_reference:
            ref_tokens = self._tokenize(expected_answer or "")
            gen_tokens = self._tokenize(out_clean)

            if not ref_tokens:
                notes = "Reference answer has no words longer than two characters; overlap cannot be scored."
            else:
                overlap = len(ref_tokens.intersection(gen_tokens))
                accuracy = round(min(1.0, overlap / len(ref_tokens)), 4)

                # Groundedness checks if response maintains reference domain terms
                groundedness = round(min(1.0, (overlap + 2) / (len(ref_tokens) + 2)), 4)
                if "hallucination" in out_clean.lower() or "error" in out_clean.lower():
                    groundedness = max(0.0, groundedness - 0.4)
        else:
            notes = "No expected answer: accuracy and groundedness are not scored."

        return EvaluationScore(
            score_id=score_id,
            execution_id=execution_id,
            accuracy=accuracy,
            groundedness=groundedness,
            format_adherence=format_adherence,
            evaluator_type="RUBRIC_HEURISTIC",
            notes=notes,
        )

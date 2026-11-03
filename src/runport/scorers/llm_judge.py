"""LLM-as-a-judge evaluation harness for Runport.

Offline Rule: Live model judge calls are never made during automated test suites.
The judge harness uses deterministic local judge functions or mocks in offline mode.
"""

import json
import re
from typing import Any, Callable, Dict, List, Optional

from runport.scorers.base import BaseScorer, ScoreResult

DEFAULT_JUDGE_RUBRIC = """You are an impartial expert evaluator. Grade the following candidate response against the reference answer and ground truth context.

[Input Query]:
{query}

[Ground Truth Context]:
{context}

[Reference Answer]:
{reference}

[Candidate Response]:
{candidate}

Evaluate the candidate on:
1. Groundedness (does the response hallucinate beyond context?)
2. Accuracy (does it match factual claims in reference?)
3. Completeness (did it answer the query fully?)

Output your evaluation strictly as JSON:
{{
  "score": <integer from 1 to 5>,
  "grounded": <true or false>,
  "reasoning": "<concise explanation>"
}}
"""


class LLMJudgeScorer(BaseScorer):
    """Pointwise or pairwise LLM judge evaluator with structured JSON output."""

    def __init__(
        self,
        judge_fn: Optional[Callable[[str], str]] = None,
        rubric_template: str = DEFAULT_JUDGE_RUBRIC,
        name: str = "llm_judge",
    ):
        super().__init__(name=name)
        self.judge_fn = judge_fn
        self.rubric_template = rubric_template

    def build_judge_prompt(
        self,
        predicted: str,
        expected: str,
        query: str = "",
        context: str = "",
    ) -> str:
        """Format the judge rubric prompt with evaluation cases."""
        return self.rubric_template.format(
            query=query,
            context=context,
            reference=expected,
            candidate=predicted,
        )

    def score(
        self,
        predicted: Any,
        expected: Any,
        context: Optional[Dict[str, Any]] = None,
    ) -> ScoreResult:
        if predicted is None or expected is None:
            return ScoreResult(
                metric_name=self.name,
                score=None,
                details={"reason": "Missing candidate prediction or reference answer"},
            )

        ctx = context or {}
        query = str(ctx.get("query", ""))
        context_text = str(ctx.get("context", ""))

        prompt = self.build_judge_prompt(
            predicted=str(predicted),
            expected=str(expected),
            query=query,
            context=context_text,
        )

        if self.judge_fn is None:
            # In offline test environment without configured judge function, return uncomputed/None
            return ScoreResult(
                metric_name=self.name,
                score=None,
                details={"reason": "No judge function configured in offline mode"},
            )

        raw_response = self.judge_fn(prompt)
        parsed = self._parse_judge_response(raw_response)

        raw_score = parsed.get("score")
        if raw_score is None:
            return ScoreResult(
                metric_name=self.name,
                score=None,
                passed=False,
                details={"raw_response": raw_response, "parse_error": "No score found in judge output"},
            )

        # Normalize 1-5 scale to 0.0 - 1.0
        normalized_score = max(0.0, min(1.0, (float(raw_score) - 1.0) / 4.0))

        return ScoreResult(
            metric_name=self.name,
            score=normalized_score,
            passed=(normalized_score >= 0.75),
            details={
                "raw_score_1_to_5": int(raw_score),
                "grounded": parsed.get("grounded", True),
                "reasoning": parsed.get("reasoning", ""),
            },
        )

    def _parse_judge_response(self, text: str) -> Dict[str, Any]:
        """Extract structured JSON from judge output."""
        cleaned = text.strip()
        # Strip markdown fences if present
        if "```json" in cleaned:
            cleaned = cleaned.split("```json")[1].split("```")[0].strip()
        elif "```" in cleaned:
            cleaned = cleaned.split("```")[1].split("```")[0].strip()

        try:
            return json.loads(cleaned)
        except Exception:
            # Fallback regex extraction for score
            m = re.search(r'"score"\s*:\s*([1-5])', text)
            if m:
                return {"score": int(m.group(1)), "reasoning": "Extracted via regex fallback"}
            return {}


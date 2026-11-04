"""Scoring and evaluation metric schemas."""

from typing import Optional
from pydantic import BaseModel, Field, model_validator


class EvaluationScore(BaseModel):
    """Rubric-based evaluation scores for model output against ground truth."""

    score_id: str = Field(description="Unique evaluation score ID")
    execution_id: str = Field(description="Associated ModelExecutionRecord ID")
    # None means "not measured" (for example, no expected answer to score against). Never 0.
    accuracy: Optional[float] = Field(default=None, ge=0.0, le=1.0, description="Factual correctness against verified reference")
    groundedness: Optional[float] = Field(default=None, ge=0.0, le=1.0, description="Absence of hallucinated or external claims")
    format_adherence: float = Field(ge=0.0, le=1.0, description="Compliance with structured output requirements")
    overall_score: Optional[float] = Field(
        default=None, ge=0.0, le=1.0, description="Weighted composite score; None when accuracy or groundedness is unmeasured"
    )
    evaluator_type: str = Field(default="RUBRIC_HEURISTIC", description="Evaluation method (e.g. LLM_JUDGE, HUMAN_EXPERT, RUBRIC_HEURISTIC)")
    notes: Optional[str] = Field(default=None, description="Diagnostic notes or justification")

    @model_validator(mode="before")
    @classmethod
    def calculate_default_overall(cls, data: dict) -> dict:
        if isinstance(data, dict) and "overall_score" not in data:
            acc, grd, fmt = data.get("accuracy"), data.get("groundedness"), data.get("format_adherence")
            if acc is None or grd is None or fmt is None:
                # Invariant: a composite of unmeasured parts is itself unmeasured, never a partial sum.
                data["overall_score"] = None
            else:
                # Default weighting: 50% accuracy, 35% groundedness, 15% format
                data["overall_score"] = round(0.50 * float(acc) + 0.35 * float(grd) + 0.15 * float(fmt), 4)
        return data

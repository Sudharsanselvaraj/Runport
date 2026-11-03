"""Runport scoring framework and statistical evaluation metrics."""

from runport.scorers.base import BaseScorer, ScoreResult
from runport.scorers.classification import (
    AccuracyScorer,
    BrierScoreScorer,
    ClassificationReport,
    ClassificationReportScorer,
)
from runport.scorers.extraction import FieldMatchScorer, JSONSchemaScorer
from runport.scorers.generation import KeywordContainmentScorer, TokenOverlapScorer
from runport.scorers.llm_judge import LLMJudgeScorer
from runport.scorers.match import ExactMatchScorer, RegexMatchScorer
from runport.scorers.performance import CostPer1kScorer, LatencyP95Scorer
from runport.scorers.stats import boot_ci, cohen_kappa, holm, pct, prf, wilson

__all__ = [
    "BaseScorer",
    "ScoreResult",
    "AccuracyScorer",
    "BrierScoreScorer",
    "ClassificationReport",
    "ClassificationReportScorer",
    "ExactMatchScorer",
    "RegexMatchScorer",
    "LatencyP95Scorer",
    "CostPer1kScorer",
    "JSONSchemaScorer",
    "FieldMatchScorer",
    "KeywordContainmentScorer",
    "TokenOverlapScorer",
    "LLMJudgeScorer",
    "wilson",
    "boot_ci",
    "cohen_kappa",
    "holm",
    "pct",
    "prf",
]

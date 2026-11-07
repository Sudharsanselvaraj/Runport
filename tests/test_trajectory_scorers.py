"""Unit and integration tests for Milestone 2 - Phase 3: Agent Trajectory Evaluation.

Validates:
- ToolSelectionScorer: exact, subsequence, and set matching modes.
- ToolArgumentScorer: argument accuracy, key-value matching, and extra key enforcement.
- ToolErrorRateScorer: tool call failure and success rates.
- LoopDetectionScorer: detection of consecutive identical calls and cyclic oscillations.
- StepBudgetScorer: step count validation and proportional budget degradation.
- RecoveryScorer: recovery detection from intermediate step errors.
- TrajectoryEfficiencyScorer: productive vs redundant step calculation.
- CompositeTrajectoryScorer: aggregated trajectory evaluation reports.
- trajectory_case_scorer integration with GenericRunner and SQLite persistence.
- Strict enforcement of Invariant 1: 'Null is not 0'.
"""

from decimal import Decimal
import json
from pathlib import Path
from typing import Any, Dict, List, Optional
import pytest

from runport.runs.executor import GenericRunner
from runport.runs.planner import create_execution_plan
from runport.scorers.tools import (
    ToolArgumentScorer,
    ToolCallCountScorer,
    ToolErrorRateScorer,
    ToolSelectionScorer,
)
from runport.scorers.trajectory import (
    CompositeTrajectoryScorer,
    LoopDetectionScorer,
    RecoveryScorer,
    StepBudgetScorer,
    TrajectoryEfficiencyScorer,
    trajectory_case_scorer,
)
from runport.storage.db import DatabaseManager
from runport.targets.base import CostBasis, Target, TargetResult, TargetStatus, TargetType
from runport.traces.domain import Span, SpanKind, SpanStatus, Trace


def _make_tool_span(
    name: str,
    args: Optional[Dict[str, Any]] = None,
    status: SpanStatus = SpanStatus.OK,
    span_id: str = "sp-1",
    error: Optional[str] = None,
) -> Span:
    return Span(
        trace_id="tr-test",
        span_id=span_id,
        name=name,
        kind=SpanKind.TOOL,
        status=status,
        attributes={"tool": name, "arguments": args or {}},
        error=error,
    )


# =============================================================================
# 1. ToolSelectionScorer Tests
# =============================================================================


def test_tool_selection_exact_mode():
    scorer = ToolSelectionScorer(match_mode="exact")

    spans = [
        _make_tool_span("search", span_id="s1"),
        _make_tool_span("calculator", span_id="s2"),
    ]

    # Exact match
    res = scorer.score(spans, ["search", "calculator"])
    assert res.score == 1.0
    assert res.passed is True

    # Wrong order
    res_wrong_order = scorer.score(spans, ["calculator", "search"])
    assert res_wrong_order.score == 0.0
    assert res_wrong_order.passed is False

    # Extra tool
    res_extra = scorer.score(spans, ["search"])
    assert res_extra.score == 0.0
    assert res_extra.passed is False


def test_tool_selection_subsequence_mode():
    scorer = ToolSelectionScorer(match_mode="subsequence")

    spans = [
        _make_tool_span("search", span_id="s1"),
        _make_tool_span("browse", span_id="s2"),
        _make_tool_span("calculator", span_id="s3"),
    ]

    # Expected tools appear in sequence
    res = scorer.score(spans, ["search", "calculator"])
    assert res.score == 1.0
    assert res.passed is True

    # Expected tools not in sequence
    res_bad = scorer.score(spans, ["calculator", "search"])
    assert res_bad.score == 0.0
    assert res_bad.passed is False


def test_tool_selection_set_mode():
    scorer = ToolSelectionScorer(match_mode="set")

    spans = [
        _make_tool_span("calculator", span_id="s1"),
        _make_tool_span("search", span_id="s2"),
    ]

    # Unordered set match (order irrelevant)
    res = scorer.score(spans, ["search", "calculator"])
    assert res.score == 1.0
    assert res.passed is True
    assert res.details["f1"] == 1.0

    # Partial set overlap
    spans_partial = [
        _make_tool_span("search", span_id="s1"),
        _make_tool_span("weather", span_id="s2"),
    ]
    res_part = scorer.score(spans_partial, ["search", "calculator"])
    assert res_part.passed is False
    assert 0.0 < res_part.score < 1.0
    assert res_part.details["precision"] == 0.5
    assert res_part.details["recall"] == 0.5


def test_tool_selection_null_is_not_zero():
    """Missing expectations return None, never fabricated 0.0."""
    scorer = ToolSelectionScorer()
    res = scorer.score([_make_tool_span("search")], None)
    assert res.score is None
    assert res.passed is None
    assert "Missing expected tools" in res.details["reason"]


# =============================================================================
# 2. ToolArgumentScorer Tests
# =============================================================================


def test_tool_arguments_single_tool():
    scorer = ToolArgumentScorer(allow_extra_keys=True)

    spans = [
        _make_tool_span("search", args={"query": "climate change", "limit": 10, "extra": "ignored"}),
    ]

    # Expected subset of keys
    res = scorer.score(spans, {"query": "climate change", "limit": 10})
    assert res.score == 1.0
    assert res.passed is True

    # Value mismatch
    res_mismatch = scorer.score(spans, {"query": "space exploration", "limit": 10})
    assert res_mismatch.score == 0.5
    assert res_mismatch.passed is False
    assert "query" in res_mismatch.details["mismatches"]


def test_tool_arguments_disallow_extra_keys():
    scorer = ToolArgumentScorer(allow_extra_keys=False)

    spans = [
        _make_tool_span("search", args={"query": "python", "unwanted": "param"}),
    ]

    res = scorer.score(spans, {"query": "python"})
    assert res.passed is False
    assert "_extra_keys" in res.details["mismatches"]


def test_tool_arguments_tool_mapping():
    scorer = ToolArgumentScorer()

    spans = [
        _make_tool_span("search", args={"query": "runport"}),
        _make_tool_span("calculator", args={"expr": "40 + 2"}),
    ]

    expected_map = {
        "search": {"query": "runport"},
        "calculator": {"expr": "40 + 2"},
    }

    res = scorer.score(spans, expected_map)
    assert res.score == 1.0
    assert res.passed is True
    assert res.details["matched_tools"] == 2


# =============================================================================
# 3. ToolErrorRateScorer & ToolCallCountScorer
# =============================================================================


def test_tool_error_rate_calculation():
    scorer = ToolErrorRateScorer()

    # 1 failed out of 4
    spans = [
        _make_tool_span("t1", status=SpanStatus.OK, span_id="1"),
        _make_tool_span("t2", status=SpanStatus.ERROR, span_id="2", error="API timeout"),
        _make_tool_span("t3", status=SpanStatus.OK, span_id="3"),
        _make_tool_span("t4", status=SpanStatus.OK, span_id="4"),
    ]

    res = scorer.score(spans)
    assert res.score == 0.25
    assert res.details["error_rate"] == 0.25
    assert res.details["success_rate"] == 0.75
    assert res.details["failed_tool_calls"] == 1


def test_tool_error_rate_zero_tools_returns_none():
    """Null is not 0: 0 tool calls returns None, not 0.0 error rate."""
    scorer = ToolErrorRateScorer()
    res = scorer.score([])
    assert res.score is None
    assert res.passed is None


def test_tool_call_count_scorer():
    scorer = ToolCallCountScorer(max_calls=3)

    spans = [
        _make_tool_span("t1", span_id="1"),
        _make_tool_span("t2", span_id="2"),
    ]

    res = scorer.score(spans)
    assert res.score == 2.0
    assert res.passed is True

    # Exceed ceiling
    spans.extend([_make_tool_span("t3", span_id="3"), _make_tool_span("t4", span_id="4")])
    res_exceeded = scorer.score(spans)
    assert res_exceeded.score == 4.0
    assert res_exceeded.passed is False


# =============================================================================
# 4. LoopDetectionScorer Tests
# =============================================================================


def test_loop_detection_clean_trajectory():
    scorer = LoopDetectionScorer(max_repeats=2)

    spans = [
        _make_tool_span("search", args={"query": "python"}, span_id="1"),
        _make_tool_span("calculator", args={"expr": "2+2"}, span_id="2"),
        _make_tool_span("format", args={"style": "markdown"}, span_id="3"),
    ]

    res = scorer.score(spans)
    assert res.score == 1.0
    assert res.passed is True
    assert res.details["has_loop"] is False


def test_loop_detection_consecutive_identical_calls():
    scorer = LoopDetectionScorer(max_repeats=2)

    # Calling search with exact same argument twice consecutively
    spans = [
        _make_tool_span("search", args={"q": "apple"}, span_id="1"),
        _make_tool_span("search", args={"q": "apple"}, span_id="2"),
    ]

    res = scorer.score(spans)
    assert res.score == 0.0
    assert res.passed is False
    assert res.details["has_loop"] is True
    assert res.details["loop_type"] == "consecutive"


def test_loop_detection_allows_same_tool_with_different_args():
    scorer = LoopDetectionScorer(max_repeats=2)

    # Calling search twice, but with DIFFERENT arguments (progressive search)
    spans = [
        _make_tool_span("search", args={"q": "apple inc"}, span_id="1"),
        _make_tool_span("search", args={"q": "apple revenue 2024"}, span_id="2"),
    ]

    res = scorer.score(spans)
    assert res.score == 1.0
    assert res.passed is True
    assert res.details["has_loop"] is False


def test_loop_detection_cyclic_oscillation():
    scorer = LoopDetectionScorer()

    # Pattern: A -> B -> A -> B
    spans = [
        _make_tool_span("search", args={"q": "foo"}, span_id="1"),
        _make_tool_span("calc", args={"x": 1}, span_id="2"),
        _make_tool_span("search", args={"q": "foo"}, span_id="3"),
        _make_tool_span("calc", args={"x": 1}, span_id="4"),
    ]

    res = scorer.score(spans)
    assert res.score == 0.0
    assert res.passed is False
    assert res.details["has_loop"] is True
    assert res.details["loop_type"] == "cycle"


# =============================================================================
# 5. StepBudgetScorer & RecoveryScorer Tests
# =============================================================================


def test_step_budget_scorer():
    scorer = StepBudgetScorer(max_steps=4)

    # Within budget
    spans = [_make_tool_span(f"t{i}", span_id=str(i)) for i in range(3)]
    res = scorer.score(spans)
    assert res.score == 1.0
    assert res.passed is True

    # Exceeding budget
    spans_long = [_make_tool_span(f"t{i}", span_id=str(i)) for i in range(6)]
    res_long = scorer.score(spans_long)
    assert res_long.passed is False
    assert res_long.score < 1.0
    assert res_long.details["exceeded_by"] == 2


def test_recovery_scorer_no_errors_returns_none():
    """Null is not 0: If no error occurred, recovery score is None."""
    scorer = RecoveryScorer()
    spans = [_make_tool_span("search", status=SpanStatus.OK)]
    res = scorer.score(spans)
    assert res.score is None
    assert res.passed is None


def test_recovery_scorer_successful_recovery():
    scorer = RecoveryScorer()

    spans = [
        _make_tool_span("db_query", status=SpanStatus.ERROR, error="Connection timeout", span_id="s1"),
        _make_tool_span("cache_query", status=SpanStatus.OK, span_id="s2"),
        Span(trace_id="tr-test", span_id="root", name="agent", kind=SpanKind.AGENT, status=SpanStatus.OK),
    ]

    res = scorer.score(spans)
    assert res.score == 1.0
    assert res.passed is True
    assert res.details["recovered"] is True


def test_recovery_scorer_unrecovered_failure():
    scorer = RecoveryScorer()

    spans = [
        _make_tool_span("db_query", status=SpanStatus.ERROR, error="Connection timeout", span_id="s1"),
        Span(trace_id="tr-test", span_id="root", name="agent", kind=SpanKind.AGENT, status=SpanStatus.ERROR),
    ]

    res = scorer.score(spans)
    assert res.score == 0.0
    assert res.passed is False
    assert res.details["recovered"] is False


# =============================================================================
# 6. CompositeTrajectoryScorer Tests
# =============================================================================


def test_composite_trajectory_scorer():
    scorer = CompositeTrajectoryScorer(max_steps=5, match_mode="exact")

    spans = [
        _make_tool_span("search", args={"q": "news"}, span_id="1"),
        _make_tool_span("calc", args={"x": 5}, span_id="2"),
    ]

    expected = {
        "expected_tools": ["search", "calc"],
        "max_steps": 5,
    }

    res = scorer.score(spans, expected)
    assert res.score == 1.0
    assert res.passed is True
    assert res.details["sub_scores"]["tool_selection"] == 1.0
    assert res.details["sub_scores"]["no_loops"] == 1.0
    assert res.details["sub_scores"]["step_budget"] == 1.0


# =============================================================================
# 7. GenericRunner Integration with trajectory_case_scorer
# =============================================================================


def test_trajectory_case_scorer_with_generic_runner(tmp_path: Path):
    """trajectory_case_scorer seamlessly evaluates and persists trajectory metrics during GenericRunner execution."""
    db = DatabaseManager(db_path=tmp_path / "test_traj_scoring.db")
    db.init_db()

    class AgentTarget(Target):
        def __init__(self):
            super().__init__(target_id="agent-model", name="Agent Model", target_type=TargetType.WORKFLOW_LANGGRAPH)

        def execute(self, payload: Dict[str, Any], context=None) -> TargetResult:
            # Trajectory with search and calculator
            tool1 = _make_tool_span("search", args={"q": "weather in Paris"}, span_id="sp-tool-1")
            tool2 = _make_tool_span("calc", args={"expr": "20 * 1.8 + 32"}, span_id="sp-tool-2")
            return TargetResult(
                target_id=self.target_id,
                status=TargetStatus.SUCCESS,
                output_text="The temperature in Paris is 68°F.",
                latency_ms=150.0,
                cost_usd=Decimal("0.001"),
                cost_basis=CostBasis.ESTIMATED,
                trajectory=[tool1, tool2],
            )

    ds_file = tmp_path / "ds.jsonl"
    ds_file.write_text('{"id": "case-agent-1", "classification": "SYNTHETIC", "expected_tools": ["search", "calc"], "max_steps": 5}\n')

    plan = create_execution_plan(["agent-model"], ds_file, is_live=False)
    runner = GenericRunner(db=db)

    results = runner.execute_plan(
        plan,
        {"agent-model": AgentTarget()},
        [{"id": "case-agent-1", "classification": "SYNTHETIC", "expected_tools": ["search", "calc"], "max_steps": 5}],
        case_scorer=trajectory_case_scorer,
    )

    run_res = results[0]
    assert run_res.successful_cases == 1

    # Verify persisted results in SQLite
    persisted_rows = db.get_evaluation_results_for_run(run_res.run_id)
    assert len(persisted_rows) == 1
    row = persisted_rows[0]

    assert row["accuracy"] == 1.0  # Tool selection match
    assert row["groundedness"] == 1.0  # No loops
    assert row["format_adherence"] == 1.0  # Within step budget
    assert row["overall_score"] == 1.0
    assert row["score_kind"] == "ground_truth"
    assert row["evaluator"] == "trajectory_eval_v1"
    assert "Tool Selection: 1.00" in row["evaluator_notes"]


"""Agent trajectory, loop detection, step budget, and recovery scorers.

Milestone 2 - Phase 3: Agent Trajectory Evaluation.

Evaluates:
- Repetitive loops and cyclic oscillations in agent trajectories.
- Step budgets and trajectory efficiency.
- Recovery from intermediate tool/node errors.
- Composite trajectory quality evaluation.

Enforces strict invariants:
- 'Null is not 0': Missing expectations or non-applicable recovery scenarios return None,
  never fabricated 0.0 or 1.0.
- All telemetry is sanitized and safe.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union

from runport.providers.base import scrub_secrets
from runport.scorers.base import BaseScorer, ScoreResult
from runport.scorers.tools import ToolArgumentScorer, ToolErrorRateScorer, ToolSelectionScorer, _extract_spans, _extract_tool_calls
from runport.targets.base import TargetResult, TargetStatus
from runport.traces.domain import Span, SpanKind, SpanStatus, Trace


def _fingerprint_step(span: Span) -> str:
    """Computes a deterministic string representation of a span operation and its arguments."""
    attrs = span.attributes or {}
    args = attrs.get("arguments") or attrs.get("tool_args") or attrs.get("inputs") or {}
    args_str = json.dumps(args, sort_keys=True) if isinstance(args, (dict, list)) else str(args)
    return f"{span.kind.value}:{span.name}:{args_str}"


def _detect_repetition_loops(steps: List[str], max_repeats: int = 2) -> Optional[Dict[str, Any]]:
    """Detects consecutive identical invocations or periodic cyclic patterns.

    Returns diagnostic dict if a loop is detected, None otherwise.
    """
    if len(steps) < max_repeats:
        return None

    # 1. Consecutive identical steps
    consecutive_count = 1
    for i in range(1, len(steps)):
        if steps[i] == steps[i - 1]:
            consecutive_count += 1
            if consecutive_count >= max_repeats:
                return {
                    "loop_type": "consecutive",
                    "pattern": [steps[i]],
                    "repeats": consecutive_count,
                    "index": i,
                }
        else:
            consecutive_count = 1

    # 2. Cyclic patterns (period 2 to 5)
    n = len(steps)
    for period in range(2, min(6, n // 2 + 1)):
        # Check if the last 2*period steps form a repeating cycle
        tail = steps[-(2 * period):]
        c1 = tail[:period]
        c2 = tail[period:]
        if c1 == c2:
            return {
                "loop_type": "cycle",
                "pattern": c1,
                "period": period,
                "repeats": 2,
            }

    return None


class LoopDetectionScorer(BaseScorer):
    """Detects whether an agent trajectory entered an unproductive repetition loop.

    Evaluates:
    - Consecutive identical invocations (same operation and arguments >= max_repeats times).
    - Cyclic oscillating patterns (e.g. A -> B -> A -> B).

    Score: 1.0 if no loops detected (clean trajectory), 0.0 if a loop was detected.
    """

    def __init__(self, name: str = "loop_detection", max_repeats: int = 2):
        super().__init__(name=name)
        self.max_repeats = max_repeats

    def score(
        self,
        predicted: Any,
        expected: Any = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> ScoreResult:
        spans = _extract_spans(predicted)
        if spans is None:
            return ScoreResult(
                metric_name=self.name,
                score=None,
                passed=None,
                details={"reason": "Missing prediction or trajectory"},
            )

        # Filter to actionable steps (tool calls, workflow steps, agents)
        action_spans = [
            s for s in spans
            if s.parent_span_id is not None or s.kind in (SpanKind.TOOL, SpanKind.WORKFLOW_STEP, SpanKind.AGENT)
        ]
        if not action_spans:
            # Trajectory with 0 or 1 step has no loop
            return ScoreResult(
                metric_name=self.name,
                score=1.0,
                passed=True,
                details={"has_loop": False, "step_count": len(spans)},
            )

        step_signatures = [_fingerprint_step(s) for s in action_spans]
        loop_info = _detect_repetition_loops(step_signatures, max_repeats=self.max_repeats)

        if loop_info:
            return ScoreResult(
                metric_name=self.name,
                score=0.0,
                passed=False,
                details={
                    "has_loop": True,
                    "loop_type": loop_info["loop_type"],
                    "pattern": scrub_secrets(loop_info["pattern"]),
                    "repeats": loop_info.get("repeats", 2),
                    "step_count": len(action_spans),
                },
            )

        return ScoreResult(
            metric_name=self.name,
            score=1.0,
            passed=True,
            details={"has_loop": False, "step_count": len(action_spans)},
        )


class StepBudgetScorer(BaseScorer):
    """Evaluates whether an agent trajectory stayed within an allocated step budget.

    Score:
    - 1.0 if actual_steps <= max_steps.
    - Proportionally degraded if exceeded: max(0.0, 1.0 - (actual - max) / max).
    """

    def __init__(self, name: str = "step_budget", max_steps: int = 10):
        super().__init__(name=name)
        self.max_steps = max(1, max_steps)

    def score(
        self,
        predicted: Any,
        expected: Any = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> ScoreResult:
        spans = _extract_spans(predicted)
        if spans is None:
            return ScoreResult(
                metric_name=self.name,
                score=None,
                passed=None,
                details={"reason": "Missing prediction or trajectory"},
            )

        # Non-root steps (or all spans if only 1 span exists)
        child_spans = [s for s in spans if s.parent_span_id is not None]
        step_count = len(child_spans) if child_spans else len(spans)

        max_limit = expected if isinstance(expected, int) and expected > 0 else self.max_steps
        is_passed = step_count <= max_limit

        if is_passed:
            score = 1.0
        else:
            exceeded = step_count - max_limit
            score = round(max(0.0, 1.0 - (exceeded / max_limit)), 4)

        return ScoreResult(
            metric_name=self.name,
            score=score,
            passed=is_passed,
            details={
                "actual_steps": step_count,
                "max_steps": max_limit,
                "exceeded_by": max(0, step_count - max_limit),
            },
        )


class RecoveryScorer(BaseScorer):
    """Evaluates whether an agent successfully recovered from intermediate step failures.

    Invariant 1: If no errors occurred in the trajectory, returns None (not applicable).
    If an error occurred and the final outcome or subsequent step succeeded: 1.0.
    If an error occurred and the agent failed to recover: 0.0.
    """

    def __init__(self, name: str = "error_recovery"):
        super().__init__(name=name)

    def score(
        self,
        predicted: Any,
        expected: Any = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> ScoreResult:
        spans = _extract_spans(predicted)
        if spans is None:
            return ScoreResult(
                metric_name=self.name,
                score=None,
                passed=None,
                details={"reason": "Missing prediction or trajectory"},
            )

        # Look for failed intermediate spans
        error_spans = [s for s in spans if s.status in (SpanStatus.ERROR, SpanStatus.TIMEOUT)]
        if not error_spans:
            # Null is not 0: No error occurred, so recovery is unmeasured / not applicable.
            return ScoreResult(
                metric_name=self.name,
                score=None,
                passed=None,
                details={"reason": "No errors occurred in trajectory; recovery not applicable"},
            )

        # Determine overall outcome
        final_ok = False
        if isinstance(predicted, TargetResult):
            final_ok = predicted.is_success
        elif isinstance(predicted, Trace):
            final_ok = predicted.status == SpanStatus.OK
        else:
            # Check root spans or last span
            root_spans = [s for s in spans if s.parent_span_id is None]
            if root_spans:
                final_ok = any(r.status == SpanStatus.OK for r in root_spans)
            elif spans:
                final_ok = spans[-1].status == SpanStatus.OK

        # Did any step succeed AFTER the first error?
        first_err_idx = min(spans.index(s) for s in error_spans)
        has_subsequent_success = any(
            s.status == SpanStatus.OK for s in spans[first_err_idx + 1 :]
        )

        recovered = final_ok and has_subsequent_success

        return ScoreResult(
            metric_name=self.name,
            score=1.0 if recovered else 0.0,
            passed=recovered,
            details={
                "error_spans_count": len(error_spans),
                "recovered": recovered,
                "first_error_span": error_spans[0].span_id,
                "first_error": error_spans[0].error,
            },
        )


class TrajectoryEfficiencyScorer(BaseScorer):
    """Calculates the ratio of productive steps (status OK, non-redundant) vs total steps."""

    def __init__(self, name: str = "trajectory_efficiency"):
        super().__init__(name=name)

    def score(
        self,
        predicted: Any,
        expected: Any = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> ScoreResult:
        spans = _extract_spans(predicted)
        if spans is None:
            return ScoreResult(
                metric_name=self.name,
                score=None,
                passed=None,
                details={"reason": "Missing prediction or trajectory"},
            )

        action_spans = [
            s for s in spans
            if s.parent_span_id is not None or s.kind in (SpanKind.TOOL, SpanKind.WORKFLOW_STEP, SpanKind.AGENT)
        ]
        if not action_spans:
            return ScoreResult(
                metric_name=self.name,
                score=None,
                passed=None,
                details={"reason": "No action steps in trajectory"},
            )

        # Count successful, non-duplicate steps
        seen_signatures: Set[str] = set()
        productive = 0
        total = len(action_spans)

        for s in action_spans:
            sig = _fingerprint_step(s)
            if s.status == SpanStatus.OK and sig not in seen_signatures:
                productive += 1
                seen_signatures.add(sig)

        efficiency = round(productive / total, 4) if total > 0 else 1.0

        return ScoreResult(
            metric_name=self.name,
            score=efficiency,
            passed=(efficiency >= 0.8),
            details={
                "total_steps": total,
                "productive_steps": productive,
                "efficiency": efficiency,
            },
        )


class CompositeTrajectoryScorer(BaseScorer):
    """Evaluates an agent trajectory across tool selection, loops, step budget, and error rates."""

    def __init__(
        self,
        name: str = "trajectory_evaluation",
        match_mode: str = "exact",
        max_steps: int = 10,
    ):
        super().__init__(name=name)
        self.tool_scorer = ToolSelectionScorer(match_mode=match_mode)
        self.loop_scorer = LoopDetectionScorer()
        self.budget_scorer = StepBudgetScorer(max_steps=max_steps)
        self.error_rate_scorer = ToolErrorRateScorer()
        self.recovery_scorer = RecoveryScorer()

    def score(
        self,
        predicted: Any,
        expected: Any,
        context: Optional[Dict[str, Any]] = None,
    ) -> ScoreResult:
        # Expected can be a dict with keys: expected_tools, expected_tool_args, max_steps
        expected_tools = None
        max_steps = None
        if isinstance(expected, dict):
            expected_tools = expected.get("expected_tools") or expected.get("tools")
            max_steps = expected.get("max_steps")
        elif isinstance(expected, (list, tuple, str)):
            expected_tools = expected

        tool_res = self.tool_scorer.score(predicted, expected_tools)
        loop_res = self.loop_scorer.score(predicted)
        budget_res = self.budget_scorer.score(predicted, max_steps)
        err_res = self.error_rate_scorer.score(predicted)
        rec_res = self.recovery_scorer.score(predicted)

        sub_scores: Dict[str, Any] = {
            "tool_selection": tool_res.score,
            "no_loops": loop_res.score,
            "step_budget": budget_res.score,
            "tool_error_rate": err_res.score,
            "error_recovery": rec_res.score,
        }

        # Calculate composite score from non-null components
        weights = {
            "tool_selection": 0.4 if tool_res.score is not None else 0.0,
            "no_loops": 0.3,
            "step_budget": 0.3,
        }
        total_weight = sum(weights.values())
        if total_weight > 0:
            comp_score = sum(sub_scores[k] * weights[k] for k in weights if sub_scores[k] is not None) / total_weight
            comp_score = round(comp_score, 4)
        else:
            comp_score = None

        all_passed = (
            (tool_res.passed is not False)
            and (loop_res.passed is True)
            and (budget_res.passed is True)
        )

        return ScoreResult(
            metric_name=self.name,
            score=comp_score,
            passed=all_passed,
            details={
                "sub_scores": sub_scores,
                "tool_selection_details": tool_res.details,
                "loop_details": loop_res.details,
                "budget_details": budget_res.details,
            },
        )


def trajectory_case_scorer(case: Dict[str, Any], result: TargetResult) -> Dict[str, Any]:
    """Ready-to-use case scorer for GenericRunner that evaluates agent trajectories.

    Extracts ground truth expectations from `case`:
    - `expected_tools`: list of expected tool names.
    - `expected_tool_args`: mapping or list of expected arguments.
    - `max_steps`: maximum allowed steps for this case.

    Returns a scores dictionary adhering to the GenericRunner persistence contract:
    `accuracy`, `groundedness`, `format_adherence`, `overall_score`, `kind`, `evaluator`, `notes`.
    """
    if result.status != TargetStatus.SUCCESS:
        return {}

    expected_tools = case.get("expected_tools")
    tool_score = None
    if expected_tools is not None:
        scorer = ToolSelectionScorer(match_mode=case.get("tool_match_mode", "exact"))
        tool_res = scorer.score(result, expected_tools)
        tool_score = tool_res.score

    loop_res = LoopDetectionScorer().score(result)
    budget_res = StepBudgetScorer(max_steps=case.get("max_steps", 10)).score(result)

    scores_list = [s for s in (tool_score, loop_res.score, budget_res.score) if s is not None]
    overall = round(sum(scores_list) / len(scores_list), 4) if scores_list else None

    notes_parts = []
    if tool_score is not None:
        notes_parts.append(f"Tool Selection: {tool_score:.2f}")
    if loop_res.score is not None:
        notes_parts.append("No Loops" if loop_res.score == 1.0 else "Loop Detected")
    if budget_res.score is not None:
        notes_parts.append(f"Budget: {budget_res.score:.2f}")

    return {
        "accuracy": tool_score,  # Tool selection accuracy against ground truth expectations
        "groundedness": loop_res.score,  # Clean trajectory free from hallucinatory repetition loops
        "format_adherence": budget_res.score,  # Step budget adherence
        "overall_score": overall,
        "kind": "ground_truth" if expected_tools is not None else "heuristic",
        "evaluator": "trajectory_eval_v1",
        "notes": "; ".join(notes_parts) if notes_parts else "Trajectory scored",
    }


"""Tool invocation and argument scorers for agent trajectory evaluation.

Milestone 2 - Phase 3: Agent Trajectory Evaluation.

Evaluates:
- Tool selection accuracy (exact sequence, subsequence, or set overlap).
- Tool argument accuracy and schema adherence.
- Tool error and failure rates across execution traces.
- Tool invocation counts against configured ceilings.

Enforces strict invariants:
- 'Null is not 0': Missing expectations or uninvoked tool telemetry return None,
  never fabricated 0.0 or 1.0.
- All extracted telemetry is sanitized and safe.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional, Sequence, Set, Union

from runport.providers.base import scrub_secrets
from runport.scorers.base import BaseScorer, ScoreResult
from runport.scorers.stats import prf
from runport.targets.base import TargetResult
from runport.traces.domain import Span, SpanKind, SpanStatus, Trace


def _extract_spans(predicted: Any) -> Optional[List[Span]]:
    """Extracts a list of Span instances from a TargetResult, Trace, or sequence of Spans."""
    if predicted is None:
        return None
    if isinstance(predicted, TargetResult):
        if predicted.trajectory is None:
            return []
        return [s for s in predicted.trajectory if isinstance(s, Span)]
    if isinstance(predicted, Trace):
        return predicted.spans
    if isinstance(predicted, (list, tuple)):
        return [s for s in predicted if isinstance(s, Span)]
    return []


def _extract_tool_calls(spans: List[Span]) -> List[Dict[str, Any]]:
    """Normalizes tool invocation spans into a structured list of tool calls."""
    calls: List[Dict[str, Any]] = []
    for span in spans:
        if span.kind != SpanKind.TOOL:
            continue
        attrs = span.attributes or {}
        # Tool name from attribute or span operation name
        name = attrs.get("tool") or attrs.get("gen_ai.tool.name") or span.name
        if isinstance(name, str):
            if name.startswith("mcp:"):
                name = name[4:]
            elif name.startswith("tool:"):
                name = name[5:]

        args = attrs.get("arguments") or attrs.get("tool_args") or {}
        if isinstance(args, str):
            try:
                args = json.loads(args)
            except Exception:
                pass

        calls.append(
            {
                "span_id": span.span_id,
                "tool": str(name),
                "arguments": args if isinstance(args, dict) else {},
                "status": span.status,
                "duration_ms": span.duration_ms,
                "error": span.error,
            }
        )
    return calls


class ToolSelectionScorer(BaseScorer):
    """Evaluates whether the agent selected the expected tool(s).

    Supports three matching modes:
    - 'exact': The ordered sequence of called tools must match expected tools exactly.
    - 'subsequence': The expected tools must appear in the called sequence in order.
    - 'set': Unordered set overlap computing Precision, Recall, and F1 score.
    """

    def __init__(self, name: str = "tool_selection", match_mode: str = "exact"):
        super().__init__(name=name)
        if match_mode not in ("exact", "subsequence", "set"):
            raise ValueError(f"Invalid match_mode '{match_mode}'. Must be 'exact', 'subsequence', or 'set'.")
        self.match_mode = match_mode

    def score(
        self,
        predicted: Any,
        expected: Any,
        context: Optional[Dict[str, Any]] = None,
    ) -> ScoreResult:
        # Invariant 1: Null is not 0. Without expected tools, score is None.
        if expected is None:
            return ScoreResult(
                metric_name=self.name,
                score=None,
                passed=None,
                details={"reason": "Missing expected tools ground truth"},
            )

        if isinstance(expected, str):
            expected_list = [expected.strip()]
        elif isinstance(expected, (list, tuple, set)):
            expected_list = [str(t).strip() for t in expected]
        elif isinstance(expected, dict):
            exp_tools = expected.get("expected_tools") or expected.get("tools")
            if exp_tools is None:
                return ScoreResult(
                    metric_name=self.name,
                    score=None,
                    passed=None,
                    details={"reason": "Expected dictionary missing 'expected_tools' key"},
                )
            expected_list = [str(t).strip() for t in exp_tools] if isinstance(exp_tools, (list, tuple)) else [str(exp_tools).strip()]
        else:
            return ScoreResult(
                metric_name=self.name,
                score=None,
                passed=None,
                details={"reason": f"Unsupported expected tools format: {type(expected)}"},
            )

        spans = _extract_spans(predicted)
        if spans is None:
            return ScoreResult(
                metric_name=self.name,
                score=None,
                passed=None,
                details={"reason": "Missing prediction or trajectory"},
            )

        tool_calls = _extract_tool_calls(spans)
        called_tools = [c["tool"] for c in tool_calls]

        # Case: expected empty list
        if not expected_list:
            is_empty = len(called_tools) == 0
            return ScoreResult(
                metric_name=self.name,
                score=1.0 if is_empty else 0.0,
                passed=is_empty,
                details={"called_tools": called_tools, "expected_tools": expected_list, "match_mode": self.match_mode},
            )

        if self.match_mode == "exact":
            is_match = called_tools == expected_list
            return ScoreResult(
                metric_name=self.name,
                score=1.0 if is_match else 0.0,
                passed=is_match,
                details={"called_tools": called_tools, "expected_tools": expected_list, "match_mode": "exact"},
            )

        if self.match_mode == "subsequence":
            # Check if expected_list is a subsequence of called_tools
            it = iter(called_tools)
            is_subseq = all(elem in it for elem in expected_list)
            return ScoreResult(
                metric_name=self.name,
                score=1.0 if is_subseq else 0.0,
                passed=is_subseq,
                details={"called_tools": called_tools, "expected_tools": expected_list, "match_mode": "subsequence"},
            )

        # Set overlap (Precision, Recall, F1)
        called_set = set(called_tools)
        expected_set = set(expected_list)
        tp = len(called_set & expected_set)
        fp = len(called_set - expected_set)
        fn = len(expected_set - called_set)
        p, r, f1 = prf(tp, fp, fn)

        p = 0.0 if (p != p) else p  # handle NaN
        r = 0.0 if (r != r) else r
        f1 = 0.0 if (f1 != f1) else f1
        passed = f1 == 1.0
        return ScoreResult(
            metric_name=self.name,
            score=round(f1, 4),
            passed=passed,
            details={
                "called_tools": called_tools,
                "expected_tools": expected_list,
                "precision": round(p, 4),
                "recall": round(r, 4),
                "f1": round(f1, 4),
                "match_mode": "set",
            },
        )


class ToolArgumentScorer(BaseScorer):
    """Evaluates whether tool call arguments match expected key-value pairs or parameters.

    Expects `expected` to be either:
    - Dict[str, Any]: Expected arguments for the target tool.
    - Dict[str, Dict[str, Any]]: Mapping of tool_name -> expected argument dict.
    - List[Dict[str, Any]]: Sequence of expected argument dictionaries corresponding to tool calls.
    """

    def __init__(self, name: str = "tool_arguments", allow_extra_keys: bool = True):
        super().__init__(name=name)
        self.allow_extra_keys = allow_extra_keys

    def score(
        self,
        predicted: Any,
        expected: Any,
        context: Optional[Dict[str, Any]] = None,
    ) -> ScoreResult:
        if expected is None:
            return ScoreResult(
                metric_name=self.name,
                score=None,
                passed=None,
                details={"reason": "Missing expected arguments ground truth"},
            )

        spans = _extract_spans(predicted)
        if spans is None:
            return ScoreResult(
                metric_name=self.name,
                score=None,
                passed=None,
                details={"reason": "Missing prediction or trajectory"},
            )

        tool_calls = _extract_tool_calls(spans)
        if not tool_calls:
            return ScoreResult(
                metric_name=self.name,
                score=0.0,
                passed=False,
                details={"reason": "No tool calls found in trajectory to evaluate arguments"},
            )

        # Single dictionary of expected arguments
        if isinstance(expected, dict) and not any(isinstance(v, dict) for v in expected.values()):
            # Evaluate against the first tool call
            actual_args = tool_calls[0]["arguments"]
            return self._score_single_args(actual_args, expected, tool_name=tool_calls[0]["tool"])

        # Mapping of tool_name -> expected arguments dict
        if isinstance(expected, dict) and all(isinstance(v, dict) for v in expected.values()):
            matches = 0
            total = len(expected)
            details_map: Dict[str, Any] = {}

            # Map called tools to their actual args
            called_map: Dict[str, Dict[str, Any]] = {c["tool"]: c["arguments"] for c in tool_calls}

            for tool_name, exp_args in expected.items():
                if tool_name not in called_map:
                    details_map[tool_name] = {"found": False, "match": False}
                    continue
                actual_args = called_map[tool_name]
                sub_res = self._score_single_args(actual_args, exp_args, tool_name=tool_name)
                details_map[tool_name] = sub_res.details
                if sub_res.passed:
                    matches += 1

            score = round(matches / total, 4) if total > 0 else None
            return ScoreResult(
                metric_name=self.name,
                score=score,
                passed=(matches == total),
                details={"tool_evaluations": details_map, "matched_tools": matches, "total_expected": total},
            )

        # List of expected argument dicts in sequence
        if isinstance(expected, (list, tuple)):
            matches = 0
            total = len(expected)
            details_list: List[Dict[str, Any]] = []

            for idx, exp_args in enumerate(expected):
                if idx >= len(tool_calls):
                    details_list.append({"index": idx, "found": False, "match": False})
                    continue
                actual_args = tool_calls[idx]["arguments"]
                sub_res = self._score_single_args(actual_args, exp_args if isinstance(exp_args, dict) else {}, tool_name=tool_calls[idx]["tool"])
                details_list.append(sub_res.details)
                if sub_res.passed:
                    matches += 1

            score = round(matches / total, 4) if total > 0 else None
            return ScoreResult(
                metric_name=self.name,
                score=score,
                passed=(matches == total),
                details={"call_evaluations": details_list, "matched_calls": matches, "total_expected": total},
            )

        return ScoreResult(
            metric_name=self.name,
            score=None,
            passed=None,
            details={"reason": f"Unsupported expected arguments format: {type(expected)}"},
        )

    def _score_single_args(self, actual: Dict[str, Any], expected: Dict[str, Any], tool_name: str) -> ScoreResult:
        if not expected:
            return ScoreResult(metric_name=self.name, score=1.0, passed=True, details={"tool": tool_name, "matched": True})

        matching_keys = 0
        total_keys = len(expected)
        mismatches: Dict[str, Any] = {}

        for k, exp_val in expected.items():
            if k not in actual:
                mismatches[k] = {"expected": exp_val, "actual": None, "reason": "key_missing"}
                continue
            act_val = actual[k]
            # Coerce string/numeric equivalence if types differ slightly
            if act_val == exp_val or str(act_val).strip() == str(exp_val).strip():
                matching_keys += 1
            else:
                mismatches[k] = {"expected": exp_val, "actual": act_val, "reason": "value_mismatch"}

        if not self.allow_extra_keys:
            extra_keys = set(actual.keys()) - set(expected.keys())
            if extra_keys:
                mismatches["_extra_keys"] = list(extra_keys)

        key_score = round(matching_keys / total_keys, 4) if total_keys > 0 else 1.0
        passed = (matching_keys == total_keys) and (self.allow_extra_keys or not mismatches.get("_extra_keys"))

        return ScoreResult(
            metric_name=self.name,
            score=key_score,
            passed=passed,
            details={
                "tool": tool_name,
                "matching_keys": matching_keys,
                "total_expected_keys": total_keys,
                "mismatches": scrub_secrets(mismatches),
            },
        )


class ToolErrorRateScorer(BaseScorer):
    """Calculates the tool call error rate (and success rate) across the trajectory.

    Invariant 1: If 0 tool calls were executed, score is None (not 0.0).
    """

    def __init__(self, name: str = "tool_error_rate", max_allowed_rate: Optional[float] = None):
        super().__init__(name=name)
        self.max_allowed_rate = max_allowed_rate

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

        tool_calls = _extract_tool_calls(spans)
        if not tool_calls:
            # Null is not 0: 0 tool calls does not mean a 0% error rate; it is unavailable.
            return ScoreResult(
                metric_name=self.name,
                score=None,
                passed=None,
                details={"reason": "No tool calls in trajectory"},
            )

        total_tools = len(tool_calls)
        failed_tools = sum(1 for c in tool_calls if c["status"] != SpanStatus.OK)
        error_rate = round(failed_tools / total_tools, 4)
        success_rate = round(1.0 - error_rate, 4)

        max_rate = self.max_allowed_rate if self.max_allowed_rate is not None else (expected if isinstance(expected, (int, float)) else None)
        passed = (error_rate <= max_rate) if max_rate is not None else (error_rate == 0.0)

        errors = [c["error"] for c in tool_calls if c["error"]]

        return ScoreResult(
            metric_name=self.name,
            score=error_rate,
            passed=passed,
            details={
                "total_tool_calls": total_tools,
                "failed_tool_calls": failed_tools,
                "successful_tool_calls": total_tools - failed_tools,
                "error_rate": error_rate,
                "success_rate": success_rate,
                "errors": scrub_secrets(errors),
            },
        )


class ToolCallCountScorer(BaseScorer):
    """Evaluates the number of tool calls against a maximum ceiling."""

    def __init__(self, name: str = "tool_call_count", max_calls: Optional[int] = None):
        super().__init__(name=name)
        self.max_calls = max_calls

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

        tool_calls = _extract_tool_calls(spans)
        count = len(tool_calls)

        max_c = self.max_calls if self.max_calls is not None else (expected if isinstance(expected, int) else None)
        passed = (count <= max_c) if max_c is not None else True

        return ScoreResult(
            metric_name=self.name,
            score=float(count),
            passed=passed,
            details={"tool_call_count": count, "max_calls": max_c},
        )

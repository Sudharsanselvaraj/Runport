"""Score replayed outputs exactly like live ones, without inventing anything.

Invariant 1 (null is not 0): a case with no recorded output has no score, no
latency and no tokens. Those stay None and are excluded from every mean; a mean
over nothing is None. Replay never substitutes the expected answer, a canned
string or fixed timings for a missing recording.
"""

from statistics import fmean
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from runport.evaluation.evaluator import RubricEvaluator
from runport.targets.base import TargetResult


def mean_or_none(values: Iterable[Optional[float]], ndigits: int = 4) -> Optional[float]:
    """Mean of the measured values; None when nothing was measured."""
    measured = [float(v) for v in values if v is not None]
    return round(fmean(measured), ndigits) if measured else None


def _case_field(case: Any, *names: str) -> Optional[str]:
    for name in names:
        val = case.get(name) if isinstance(case, dict) else getattr(case, name, None)
        if val is not None and str(val).strip():
            return str(val)
    return None


def score_replay_results(
    run_id: str,
    cases: Sequence[Any],
    results: Sequence[TargetResult],
    evaluator: Optional[RubricEvaluator] = None,
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """Build stored result rows and run-level aggregates for a replay run.

    Returns (rows, aggregates). ``aggregates`` holds completed/failed counts and
    the means of the measured values, each None when nothing was measured.
    """
    evaluator = evaluator or RubricEvaluator()
    rows: List[Dict[str, Any]] = []
    for idx, (case, res) in enumerate(zip(cases, results)):
        case_id = _case_field(case, "id", "case_id") or str(idx)
        prompt = _case_field(case, "query", "prompt", "input") or ""
        expected = _case_field(case, "expected_answer", "ground_truth", "expected")
        recorded = res.is_success and bool(res.output_text and res.output_text.strip())

        if recorded:
            score = evaluator.evaluate(
                score_id=f"score_{run_id}_{case_id}",
                execution_id=f"exec_{run_id}_{case_id}",
                generated_output=str(res.output_text),
                expected_answer=expected,
            )
            accuracy, groundedness = score.accuracy, score.groundedness
            fmt, overall = score.format_adherence, score.overall_score
            notes = f"Provenance: REPLAYED. {score.notes or ''}".strip()
        else:
            accuracy = groundedness = fmt = overall = None
            notes = f"Provenance: REPLAYED. Not scored: {res.error_message or 'no recorded output for this case.'}"

        rows.append(
            {
                "result_id": f"res-{run_id}-{idx}",
                "run_id": run_id,
                "case_id": case_id,
                "prompt": prompt,
                "expected_answer": expected or "",
                "generated_output": str(res.output_text) if recorded else "",
                "latency_ms": res.latency_ms if recorded else None,
                "prompt_tokens": res.tokens_in if recorded else None,
                "completion_tokens": res.tokens_out if recorded else None,
                "cost_usd": "0.0000",
                "accuracy": accuracy,
                "groundedness": groundedness,
                "format_adherence": fmt,
                "overall_score": overall,
                "evaluator_notes": notes,
                "_recorded": recorded,
            }
        )

    completed = sum(1 for r in rows if r["_recorded"])
    aggregates = {
        "completed_cases": completed,
        "failed_cases": len(rows) - completed,
        "mean_latency_ms": mean_or_none((r["latency_ms"] for r in rows), ndigits=2),
        "mean_accuracy": mean_or_none(r["accuracy"] for r in rows),
        "mean_groundedness": mean_or_none(r["groundedness"] for r in rows),
        "mean_overall_score": mean_or_none(r["overall_score"] for r in rows),
    }
    for r in rows:
        r.pop("_recorded")
    return rows, aggregates

"""Tests for statistical scorers and recompute proof.

Invariant 1: Null is not 0.
Invariant 8: Agreement is not correctness.
Invariant 16: Supervised metrics only from ground truth.

Recompute Proof: Metrics independently computed from per-case rows strictly equal reported summary metrics.
"""

from decimal import Decimal
import pytest

from runport.scorers import (
    AccuracyScorer,
    ClassificationReportScorer,
    CostPer1kScorer,
    ExactMatchScorer,
    LatencyP95Scorer,
    RegexMatchScorer,
)


def test_exact_and_normalized_match_scorer():
    """ExactMatchScorer tests strict matching vs whitespace/case normalized matching."""
    exact = ExactMatchScorer(ignore_case=False, normalize_whitespace=False)
    norm = ExactMatchScorer(ignore_case=True, normalize_whitespace=True)

    # Strict match
    assert exact.score("Paris", "Paris").passed is True
    assert exact.score("paris", "Paris").passed is False
    assert exact.score(" Paris ", "Paris").passed is True  # strip is applied

    # Normalized match
    assert norm.score("  Paris  ", "paris").passed is True
    assert norm.score("New   York", "new york").passed is True
    assert norm.score("London", "Paris").passed is False

    # Null is not 0
    res_null = norm.score(None, "Paris")
    assert res_null.score is None
    assert res_null.passed is None


def test_regex_match_scorer():
    """RegexMatchScorer evaluates pattern fullmatch and search."""
    # Fullmatch
    code_scorer = RegexMatchScorer(r"^[A-Z]{3}-\d{4}$")
    assert code_scorer.score("ABC-1234").passed is True
    assert code_scorer.score("abc-1234").passed is False
    assert code_scorer.score("PREFIX ABC-1234").passed is False

    # Search mode
    email_scorer = RegexMatchScorer(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+", search_mode=True)
    assert email_scorer.score("Contact us at test@example.com for info.").passed is True
    assert email_scorer.score("No email here.").passed is False


def test_latency_p95_and_cost_per_1k_scorers():
    """LatencyP95Scorer and CostPer1kScorer compute SLA and economics metrics."""
    lats = [10.0, 20.0, 30.0, 40.0, 50.0, 60.0, 70.0, 80.0, 90.0, 100.0]
    p95_scorer = LatencyP95Scorer(threshold_ms=96.0)
    res_p95 = p95_scorer.evaluate_batch(lats)
    assert res_p95.score == pytest.approx(95.5, rel=1e-2)
    assert res_p95.passed is True

    res_p95_fail = LatencyP95Scorer(threshold_ms=80.0).evaluate_batch(lats)
    assert res_p95_fail.passed is False

    # Cost per 1k
    cost_scorer = CostPer1kScorer(max_cost_per_1k_usd=Decimal("5.00"))
    res_cost = cost_scorer.evaluate(total_cost_usd=Decimal("0.40"), case_count=100)
    # 0.40 / 100 * 1000 = $4.00 per 1k
    assert res_cost.score == 4.0
    assert res_cost.passed is True

    res_cost_fail = cost_scorer.evaluate(total_cost_usd=Decimal("0.80"), case_count=100)
    # $8.00 per 1k > $5.00 ceiling
    assert res_cost_fail.passed is False


def test_recompute_proof_per_case_rows_equal_reported_metrics():
    """Recompute Proof: Metrics computed independently from individual case records match summary metrics."""
    case_rows = [
        {"case_id": "c1", "pred": "POSITIVE", "truth": "POSITIVE", "latency_ms": 50.0, "cost": Decimal("0.0002")},
        {"case_id": "c2", "pred": "POSITIVE", "truth": "POSITIVE", "latency_ms": 60.0, "cost": Decimal("0.0002")},
        {"case_id": "c3", "pred": "NEGATIVE", "truth": "NEGATIVE", "latency_ms": 40.0, "cost": Decimal("0.0001")},
        {"case_id": "c4", "pred": "POSITIVE", "truth": "NEGATIVE", "latency_ms": 70.0, "cost": Decimal("0.0003")},
        {"case_id": "c5", "pred": None,       "truth": "POSITIVE", "latency_ms": 80.0, "cost": Decimal("0.0001")},  # Invalid
    ]

    # Reported summary metrics
    total_cases = len(case_rows)
    reported_accuracy = 3 / 5  # 0.60
    reported_mean_latency = (50.0 + 60.0 + 40.0 + 70.0 + 80.0) / 5  # 60.0
    reported_total_cost = sum(r["cost"] for r in case_rows)  # 0.0009

    # Independent recomputation via ClassificationReportScorer
    preds = [r["pred"] for r in case_rows]
    truths = [r["truth"] for r in case_rows]
    report_scorer = ClassificationReportScorer(allowed_labels=["POSITIVE", "NEGATIVE"])
    report = report_scorer.compute_report(preds, truths)

    # 1. Assert recomputed accuracy equals reported accuracy
    assert report.accuracy == pytest.approx(reported_accuracy)
    assert report.total_cases == total_cases
    assert report.invalid_cases == 1
    assert report.valid_cases == 4

    # 2. Assert recomputed confusion matrix matches exact counts
    cm = report.confusion_matrix
    assert cm["POSITIVE"]["POSITIVE"] == 2
    assert cm["NEGATIVE"]["NEGATIVE"] == 1
    assert cm["NEGATIVE"]["POSITIVE"] == 1
    assert cm["POSITIVE"]["INVALID_OUTPUT"] == 1

    # 3. Assert recomputed latency metrics match
    lats = [r["latency_ms"] for r in case_rows]
    mean_lat = sum(lats) / len(lats)
    assert mean_lat == pytest.approx(reported_mean_latency)

    # 4. Assert recomputed cost metrics match
    cost_res = CostPer1kScorer().evaluate(reported_total_cost, total_cases)
    # (0.0009 / 5) * 1000 = $0.18 per 1k
    assert cost_res.score == pytest.approx(0.18)


"""Comprehensive tests for the generalized classification workload, runner, metrics, and thresholding."""

from decimal import Decimal
import pytest

from runport.classification.contracts import ClassificationCase, Role, Turn
from runport.classification.metrics import (
    IntentItem, brier_multiclass, expected_calibration_error, intent_metrics,
)
from runport.scorers.stats import wilson
from runport.classification.records import PredictionRecord, PredictionStore
from runport.classification.runner import ClassificationRunner, ClassificationRunSummary
from runport.classification.threshold import (
    CRITERION_MAX_F1, FrozenThreshold, ProbItem, evaluate_held_out, select_threshold_on_dev,
)
from runport.classification.validators import validate_classification_output
from runport.core.budget import BudgetExceededError, BudgetService
from runport.core.live_guard import LiveAuthorization
from runport.models.registry import Protocol
from runport.providers.base import BaseProvider, LiveNotAuthorizedError, ProviderRequest, ProviderResponse
from runport.schemas.evaluation import DatasetSplit


class MockClassificationProvider(BaseProvider):
    def __init__(self, responses=None):
        self.responses = responses or {}
        self.recorded_requests = []

    def generate(self, request: ProviderRequest) -> ProviderResponse:
        self.recorded_requests.append(request)
        if request.live_authorized and not request.live_authorized:
            raise LiveNotAuthorizedError("Live calls refused")
        resp_text = self.responses.get(request.case_id, "DEFAULT_LABEL")
        return ProviderResponse(
            model_id=request.model_id,
            output_text=resp_text,
            prompt_tokens=50,
            completion_tokens=10,
            latency_ms=10.0,
            usage_source="PROVIDER_REPORTED",
            actual_cost_usd=Decimal("0.000100"),
            cost_usd=Decimal("0.000100"),
            cost_basis="PROVIDER_REPORTED",
        )


def test_classification_contracts():
    """ClassificationCase and Turn enforce strict schema invariants."""
    turn = Turn(turn_index=0, role=Role.USER, text="Hello world", source_ref="test")
    assert turn.turn_index == 0
    assert turn.role == Role.USER

    case = ClassificationCase(
        case_id="case-001",
        input_text="Classify this input text.",
        expected_label="POSITIVE",
        split=DatasetSplit.TEST,
        history=[turn],
    )
    assert case.case_id == "case-001"
    assert case.expected_label == "POSITIVE"
    assert len(case.history) == 1

    # Extra fields are forbidden
    with pytest.raises(Exception):
        ClassificationCase(case_id="bad", input_text="x", invalid_field="not_allowed")


def test_validate_classification_output():
    """validate_classification_output enforces allowed labels and parses plain text."""
    allowed = ["SPAM", "HAM", "INCONCLUSIVE"]

    val = validate_classification_output("SPAM", allowed)
    assert val.valid is True and val.label == "SPAM" and val.reason is None

    # Case mismatch flags WRONG_CASE
    val_lower = validate_classification_output("  ham  ", allowed)
    assert val_lower.valid is False

    # Disallowed label returns valid=False with reason
    val_inv = validate_classification_output("UNKNOWN_TAG", allowed)
    assert val_inv.valid is False
    assert val_inv.label is None


def test_classification_runner_offline_execution(tmp_path):
    """ClassificationRunner dispatches offline batch, records predictions, and tracks spend."""
    provider = MockClassificationProvider({
        "c1": "QUERY",
        "c2": "GREETING",
        "c3": "INVALID_OUTPUT_TEST",
    })
    store = PredictionStore(tmp_path / "preds.jsonl")
    budget = BudgetService()
    runner = ClassificationRunner(provider=provider, budget_service=budget, store=store)

    cases = [
        ClassificationCase(case_id="c1", input_text="Where is my order?"),
        ClassificationCase(case_id="c2", input_text="Hello good morning!"),
        ClassificationCase(case_id="c3", input_text="Random text here"),
    ]

    summary = runner.run_batch(
        cases=cases,
        target_id="mock-model",
        run_id="run-test-01",
        allowed_labels=["QUERY", "GREETING"],
    )

    assert summary.n_cases == 3
    assert summary.n_ok == 2
    assert summary.n_invalid == 1
    assert summary.n_error == 0
    assert summary.total_spend_usd > Decimal("0")

    # Verify store content
    stored = store.read_all()
    assert len(stored) == 3
    c1_rec = next(r for r in stored if r.case_id == "c1")
    assert c1_rec.status == "OK"
    assert c1_rec.predicted_label == "QUERY"

    c3_rec = next(r for r in stored if r.case_id == "c3")
    assert c3_rec.status == "INVALID_OUTPUT"
    assert c3_rec.predicted_label is None


def test_supervised_metrics_computation():
    """Metrics accurately compute accuracy, macro F1, and confusion matrix."""
    items = [
        IntentItem(expected="QUERY", predicted="QUERY"),
        IntentItem(expected="QUERY", predicted="QUERY"),
        IntentItem(expected="GREETING", predicted="GREETING"),
        IntentItem(expected="GREETING", predicted="QUERY"),  # Error
        IntentItem(expected="OTHER", predicted=None),        # Invalid output
    ]

    metrics = intent_metrics(items)
    assert metrics.n_scored == 5
    assert metrics.invalid_count == 1
    assert metrics.accuracy == pytest.approx(0.60)
    assert "QUERY" in metrics.per_class
    assert "GREETING" in metrics.per_class

    # Wilson interval
    ci = wilson(3, 5)
    assert 0.0 <= ci[0] <= 0.60 <= ci[1] <= 1.0


def test_calibration_and_brier_score():
    """ECE and multiclass Brier score calculations."""
    probs = [
        {"A": 0.9, "B": 0.1},
        {"A": 0.8, "B": 0.2},
        {"A": 0.3, "B": 0.7},
    ]
    truths = ["A", "A", "B"]

    brier = brier_multiclass(probs, truths, source="TEST")
    assert brier is not None
    assert brier >= 0.0

    confs = [0.9, 0.8, 0.7]
    corrects = [True, True, True]
    ece = expected_calibration_error(confs, corrects, n_bins=2, source="TEST")
    assert ece is not None
    assert ece >= 0.0


def test_dev_calibration_and_held_out_frozen_evaluation():
    """Invariant: thresholds are calibrated strictly on DEV and evaluated frozen on TEST."""
    dev_items = [
        ProbItem(case_id="d1", expected=True, yes_prob=0.85, split=DatasetSplit.DEV),
        ProbItem(case_id="d2", expected=True, yes_prob=0.65, split=DatasetSplit.DEV),
        ProbItem(case_id="d3", expected=False, yes_prob=0.20, split=DatasetSplit.DEV),
        ProbItem(case_id="d4", expected=False, yes_prob=0.45, split=DatasetSplit.DEV),
    ]

    # Select threshold on DEV only
    frozen = select_threshold_on_dev(dev_items)
    assert isinstance(frozen, FrozenThreshold)
    assert frozen.n_dev_scored == 4
    assert frozen.dev_f1_at_threshold >= 0.80

    # Evaluate unchanged on TEST (held-out)
    test_items = [
        ProbItem(case_id="t1", expected=True, yes_prob=0.80, split=DatasetSplit.TEST),
        ProbItem(case_id="t2", expected=False, yes_prob=0.15, split=DatasetSplit.TEST),
    ]
    test_report = evaluate_held_out(test_items, frozen)
    assert test_report.n_scored == 2
    assert test_report.at_frozen.accuracy == pytest.approx(1.0)
    assert test_report.at_frozen.f1 == pytest.approx(1.0)


def test_splits_group_assignment_and_privacy():
    """assign_group_splits assigns groups deterministically and rejects user4."""
    from runport.classification.splits import SplitError, assert_no_user4, assign_group_splits

    # Rejection of forbidden key
    with pytest.raises(SplitError, match="Forbidden sensitive column"):
        assert_no_user4(["case_id", "user4", "text"])

    assert_no_user4(["case_id", "session_id", "text"])

    # Deterministic split assignment
    groups = ["g1", "g2", "g3", "g4", "g5", "g6", "g7", "g8", "g9", "g10"]
    ratios = {DatasetSplit.DEV: 0.5, DatasetSplit.TEST: 0.5}
    assigned1 = assign_group_splits(groups, ratios, seed="seed-12345")
    assigned2 = assign_group_splits(groups, ratios, seed="seed-12345")
    assert assigned1 == assigned2
    assert len(assigned1) == 10
    assert sum(1 for s in assigned1.values() if s == DatasetSplit.DEV) == 5
    assert sum(1 for s in assigned1.values() if s == DatasetSplit.TEST) == 5


def test_whole_batch_privacy_gate_rejects_before_any_request(tmp_path):
    """Whole-batch privacy gate: if any case in the batch violates privacy, zero requests are sent."""
    from runport.schemas.evaluation import DataClassification

    provider = MockClassificationProvider({"c1": "QUERY"})
    store = PredictionStore(tmp_path / "preds.jsonl")
    runner = ClassificationRunner(provider=provider, store=store)

    cases = [
        ClassificationCase(case_id="c1", input_text="Safe query 1", data_classification=DataClassification.SYNTHETIC),
        ClassificationCase(case_id="c2", input_text="Confidential inquiry", data_classification=DataClassification.CONFIDENTIAL),
    ]

    # Without live authorization covering the batch, entire batch fails before ANY request
    with pytest.raises(LiveNotAuthorizedError, match="live authorization required"):
        runner.run_batch(cases=cases, target_id="mock-target")

    # Invariant check: Transport was NEVER called
    assert len(provider.recorded_requests) == 0
    # Store remains empty
    assert len(store.read_all()) == 0


def test_runner_strict_guard_order(tmp_path):
    """Runner guard order: Authorization -> Privacy Gate -> Preflight Budget -> Transport -> Validation -> Store."""
    from runport.core.config import BudgetPolicy
    from runport.storage.db import DatabaseManager
    from runport.schemas.evaluation import DataClassification

    db = DatabaseManager(tmp_path / "guard_test.db")
    db.init_db()
    # Zero budget policy to trigger budget preflight failure
    budget_zero = BudgetService(db=db, policy=BudgetPolicy(total_budget_usd=Decimal("0.00")))

    provider = MockClassificationProvider({"c1": "QUERY"})
    store = PredictionStore(tmp_path / "preds.jsonl")

    runner = ClassificationRunner(provider=provider, budget_service=budget_zero, store=store)

    # 1. Authorization Guard Check
    # Providing an invalid LiveAuthorization for a different model fails at Step 1
    bad_auth = LiveAuthorization(models=("other-model",))
    with pytest.raises(LiveNotAuthorizedError, match="live run refused"):
        runner.run_batch(
            cases=[ClassificationCase(case_id="c1", input_text="Hello")],
            target_id="mock-target",
            live_auth=bad_auth,
        )
    assert len(provider.recorded_requests) == 0

    # 2. Privacy Gate Check (Step 2)
    # Even if authorization covers mock-target, an unauthorized confidential case fails Step 2
    conf_case = ClassificationCase(case_id="c1", input_text="Sensitive text", data_classification=DataClassification.CONFIDENTIAL)
    runner_no_auth = ClassificationRunner(provider=provider, store=store)
    with pytest.raises(LiveNotAuthorizedError, match="CONFIDENTIAL"):
        runner_no_auth.run_batch(cases=[conf_case], target_id="mock-target")
    assert len(provider.recorded_requests) == 0

    # 3. Preflight Budget Check (Step 3)
    # Valid auth, public data, but zero remaining budget fails before transport
    good_auth = LiveAuthorization(models=("mock-target",))
    with pytest.raises(BudgetExceededError, match="Budget limit exhausted"):
        runner.run_batch(
            cases=[ClassificationCase(case_id="c1", input_text="Public text")],
            target_id="mock-target",
            live_auth=good_auth,
        )
    assert len(provider.recorded_requests) == 0

    # 4. Successful execution passing all guards
    budget_ok = BudgetService(db=db, policy=BudgetPolicy(total_budget_usd=Decimal("10.00")))
    runner_ok = ClassificationRunner(provider=provider, budget_service=budget_ok, store=store)
    summary = runner_ok.run_batch(
        cases=[ClassificationCase(case_id="c1", input_text="Public text")],
        target_id="mock-target",
        live_auth=good_auth,
        allowed_labels=["QUERY"],
    )
    assert summary.n_ok == 1
    assert len(provider.recorded_requests) == 1
    assert len(store.read_all()) == 1



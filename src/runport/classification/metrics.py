"""Universal classification metrics computed exclusively from approved ground-truth labels."""

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple

from pydantic import BaseModel

INVALID = "INVALID"


class MetricsError(ValueError):
    pass


@dataclass
class ClassificationItem:
    expected: Optional[str]
    predicted: Optional[str]  # None = invalid output
    exclusion_reason: Optional[str] = None


class ClassStats(BaseModel):
    precision: Optional[float]
    recall: Optional[float]
    f1: Optional[float]
    support: int


class ClassificationMetrics(BaseModel):
    n_total: int
    n_excluded: int
    n_unlabeled: int
    n_scored: int
    invalid_count: int
    invalid_rate: Optional[float]
    accuracy: Optional[float]
    macro_f1: Optional[float]
    per_class: Dict[str, ClassStats]
    confusion: Dict[str, Dict[str, int]]


class BinaryMetrics(BaseModel):
    n_total: int
    n_scored: int
    tp: int
    fp: int
    tn: int
    fn: int
    precision: Optional[float]
    recall: Optional[float]
    f1: Optional[float]
    accuracy: Optional[float]
    false_positive_rate: Optional[float]
    false_negative_rate: Optional[float]

    @property
    def yes_precision(self) -> Optional[float]:
        return self.precision

    @property
    def yes_recall(self) -> Optional[float]:
        return self.recall

    @property
    def yes_f1(self) -> Optional[float]:
        return self.f1


def compute_classification_metrics(items: Sequence[ClassificationItem]) -> ClassificationMetrics:
    """Computes multiclass accuracy, macro F1, per-class metrics, and confusion matrix."""
    n_total = len(items)
    excluded = [it for it in items if it.exclusion_reason is not None]
    candidate = [it for it in items if it.exclusion_reason is None]
    unlabeled = [it for it in candidate if it.expected is None]
    scorable = [it for it in candidate if it.expected is not None]
    n_scored = len(scorable)

    if n_scored == 0:
        return ClassificationMetrics(
            n_total=n_total,
            n_excluded=len(excluded),
            n_unlabeled=len(unlabeled),
            n_scored=0,
            invalid_count=sum(it.predicted is None for it in scorable),
            invalid_rate=None,
            accuracy=None,
            macro_f1=None,
            per_class={},
            confusion={},
        )

    labels: Set[str] = {it.expected for it in scorable if it.expected is not None}
    for it in scorable:
        if it.predicted is not None:
            labels.add(it.predicted)

    sorted_labels = sorted(labels)
    confusion = {e: {p: 0 for p in sorted_labels + [INVALID]} for e in sorted_labels}

    invalid_count = 0
    correct = 0

    for it in scorable:
        exp = it.expected
        pred = it.predicted
        if pred is None:
            invalid_count += 1
            confusion[exp][INVALID] += 1
        else:
            confusion[exp][pred] += 1
            if exp == pred:
                correct += 1

    accuracy = correct / n_scored if n_scored > 0 else None
    invalid_rate = invalid_count / n_scored if n_scored > 0 else None

    per_class: Dict[str, ClassStats] = {}
    f1_list: List[float] = []

    for lbl in sorted(labels):
        support = sum(1 for it in scorable if it.expected == lbl)
        tp = sum(1 for it in scorable if it.expected == lbl and it.predicted == lbl)
        fp = sum(1 for it in scorable if it.expected != lbl and it.predicted == lbl)
        fn = sum(1 for it in scorable if it.expected == lbl and it.predicted != lbl)

        prec = tp / (tp + fp) if (tp + fp) > 0 else (0.0 if support > 0 else None)
        rec = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = (2 * prec * rec) / (prec + rec) if (prec is not None and rec is not None and (prec + rec) > 0) else 0.0

        per_class[lbl] = ClassStats(precision=prec, recall=rec, f1=f1, support=support)
        if support > 0:
            f1_list.append(f1)

    macro_f1 = sum(f1_list) / len(f1_list) if f1_list else None

    return ClassificationMetrics(
        n_total=n_total,
        n_excluded=len(excluded),
        n_unlabeled=len(unlabeled),
        n_scored=n_scored,
        invalid_count=invalid_count,
        invalid_rate=invalid_rate,
        accuracy=accuracy,
        macro_f1=macro_f1,
        per_class=per_class,
        confusion=confusion,
    )


def compute_binary_metrics(scorable: Sequence[Any]) -> BinaryMetrics:
    """Computes binary precision, recall, F1, FPR, FNR."""
    tp = fp = tn = fn = 0
    valid_count = 0

    pairs: List[Tuple[Optional[bool], Optional[bool]]] = []
    for item in scorable:
        if isinstance(item, tuple):
            pairs.append((item[0], item[1]))
        elif hasattr(item, "expected") and hasattr(item, "predicted"):
            pairs.append((item.expected, item.predicted))
        else:
            pairs.append((None, None))

    for exp, pred in pairs:
        if exp is None:
            continue
        if pred is None:
            fn += 1 if exp else 0
            fp += 1 if not exp else 0
            continue
        valid_count += 1
        if exp and pred:
            tp += 1
        elif not exp and pred:
            fp += 1
        elif not exp and not pred:
            tn += 1
        elif exp and not pred:
            fn += 1

    n_scored = len(pairs)
    prec = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    rec = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = (2 * prec * rec) / (prec + rec) if (prec + rec) > 0 else 0.0
    acc = (tp + tn) / n_scored if n_scored > 0 else None
    fpr = fp / (fp + tn) if (fp + tn) > 0 else 0.0
    fnr = fn / (fn + tp) if (fn + tp) > 0 else 0.0

    return BinaryMetrics(
        n_total=n_scored,
        n_scored=n_scored,
        tp=tp,
        fp=fp,
        tn=tn,
        fn=fn,
        precision=prec,
        recall=rec,
        f1=f1,
        accuracy=acc,
        false_positive_rate=fpr,
        false_negative_rate=fnr,
    )


def brier_multiclass(probs_list: Sequence[Dict[str, float]], truths: Sequence[str], source: Any = None) -> Optional[float]:
    """Computes multiclass Brier score over valid probability distributions and approved labels."""
    if not probs_list or len(probs_list) != len(truths):
        return None
    total_sq_err = 0.0
    for probs, true_label in zip(probs_list, truths):
        classes = set(probs.keys())
        classes.add(true_label)
        for c in classes:
            p = probs.get(c, 0.0)
            y = 1.0 if c == true_label else 0.0
            total_sq_err += (p - y) ** 2
    return total_sq_err / len(probs_list)


def expected_calibration_error(confs: Sequence[float], correct: Sequence[bool], n_bins: int = 10, source: Any = None) -> Optional[float]:
    """Computes Expected Calibration Error across equal-width confidence bins."""
    if not confs or len(confs) != len(correct):
        return None
    n = len(confs)
    n_bins = max(1, n_bins)
    ece = 0.0
    for b in range(n_bins):
        lo = b / n_bins
        hi = (b + 1) / n_bins
        idx = [i for i, c in enumerate(confs) if (lo <= c < hi) or (b == n_bins - 1 and c == 1.0)]
        if idx:
            bin_size = len(idx)
            bin_acc = sum(correct[i] for i in idx) / bin_size
            bin_conf = sum(confs[i] for i in idx) / bin_size
            ece += (bin_size / n) * abs(bin_acc - bin_conf)
    return ece

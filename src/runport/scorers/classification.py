"""Statistical classification metrics and calibration scorers."""

from typing import Any, Dict, List, Optional, Sequence
import math
from dataclasses import dataclass, field

from runport.scorers.base import BaseScorer, ScoreResult
from runport.scorers.stats import prf, wilson


@dataclass
class ClassificationReport:
    """Detailed multiclass evaluation report with per-class metrics and confusion matrix."""
    accuracy: float
    macro_precision: float
    macro_recall: float
    macro_f1: float
    per_class: Dict[str, Dict[str, Any]]
    confusion_matrix: Dict[str, Dict[str, int]]
    total_cases: int
    valid_cases: int
    invalid_cases: int


class ClassificationReportScorer(BaseScorer):
    """Generates complete multiclass classification reports with precision, recall, F1, and confusion matrix."""

    def __init__(self, allowed_labels: Optional[List[str]] = None, name: str = "classification_report"):
        super().__init__(name=name)
        self.allowed_labels = allowed_labels

    def compute_report(
        self,
        predictions: Sequence[Optional[str]],
        references: Sequence[str],
    ) -> ClassificationReport:
        """Computes comprehensive classification metrics from paired predictions and references."""
        if len(predictions) != len(references):
            raise ValueError(f"Length mismatch: {len(predictions)} predictions vs {len(references)} references.")

        total = len(predictions)
        if total == 0:
            return ClassificationReport(
                accuracy=0.0,
                macro_precision=0.0,
                macro_recall=0.0,
                macro_f1=0.0,
                per_class={},
                confusion_matrix={},
                total_cases=0,
                valid_cases=0,
                invalid_cases=0,
            )

        # Collect distinct labels
        labels_set = set(self.allowed_labels) if self.allowed_labels else set()
        for ref in references:
            if ref:
                labels_set.add(str(ref).strip().upper())
        for pred in predictions:
            if pred:
                labels_set.add(str(pred).strip().upper())
        labels = sorted(list(labels_set))

        # Build confusion matrix: confusion_matrix[expected][predicted]
        cm: Dict[str, Dict[str, int]] = {
            exp: {pred: 0 for pred in labels + ["INVALID_OUTPUT"]}
            for exp in labels
        }

        n_valid = 0
        n_invalid = 0
        n_correct = 0

        for pred, ref in zip(predictions, references):
            ref_clean = str(ref).strip().upper() if ref else "UNKNOWN"
            if ref_clean not in cm:
                cm[ref_clean] = {p: 0 for p in labels + ["INVALID_OUTPUT"]}

            if pred is None or (self.allowed_labels and str(pred).strip().upper() not in self.allowed_labels):
                n_invalid += 1
                cm[ref_clean]["INVALID_OUTPUT"] += 1
            else:
                n_valid += 1
                pred_clean = str(pred).strip().upper()
                cm[ref_clean][pred_clean] += 1
                if pred_clean == ref_clean:
                    n_correct += 1

        accuracy = n_correct / total if total > 0 else 0.0

        # Compute per-class precision, recall, F1, support
        per_class: Dict[str, Dict[str, Any]] = {}
        precisions = []
        recalls = []
        f1s = []

        for lbl in labels:
            # TP: expected == lbl and predicted == lbl
            tp = cm[lbl].get(lbl, 0)
            # FN: expected == lbl and predicted != lbl
            fn = sum(count for p, count in cm[lbl].items() if p != lbl)
            # FP: expected != lbl and predicted == lbl
            fp = sum(cm[exp].get(lbl, 0) for exp in labels if exp != lbl)

            support = tp + fn
            prec = tp / (tp + fp) if (tp + fp) > 0 else 0.0
            rec = tp / (tp + fn) if (tp + fn) > 0 else 0.0
            f1 = (2 * prec * rec) / (prec + rec) if (prec + rec) > 0 else 0.0

            per_class[lbl] = {
                "precision": round(prec, 4),
                "recall": round(rec, 4),
                "f1": round(f1, 4),
                "support": support,
            }
            if support > 0:
                precisions.append(prec)
                recalls.append(rec)
                f1s.append(f1)

        macro_p = sum(precisions) / len(precisions) if precisions else 0.0
        macro_r = sum(recalls) / len(recalls) if recalls else 0.0
        macro_f1 = sum(f1s) / len(f1s) if f1s else 0.0

        return ClassificationReport(
            accuracy=round(accuracy, 4),
            macro_precision=round(macro_p, 4),
            macro_recall=round(macro_r, 4),
            macro_f1=round(macro_f1, 4),
            per_class=per_class,
            confusion_matrix=cm,
            total_cases=total,
            valid_cases=n_valid,
            invalid_cases=n_invalid,
        )

    def score(
        self,
        predicted: Any,
        expected: Any,
        context: Optional[Dict[str, Any]] = None,
    ) -> ScoreResult:
        ctx = context or {}
        preds = ctx.get("predictions")
        refs = ctx.get("references")
        if preds is not None and refs is not None:
            rep = self.compute_report(preds, refs)
            return ScoreResult(
                metric_name=self.name,
                score=rep.macro_f1,
                details={
                    "accuracy": rep.accuracy,
                    "macro_f1": rep.macro_f1,
                    "macro_precision": rep.macro_precision,
                    "macro_recall": rep.macro_recall,
                    "total_cases": rep.total_cases,
                    "invalid_cases": rep.invalid_cases,
                    "per_class": rep.per_class,
                    "confusion_matrix": rep.confusion_matrix,
                },
            )
        # Single case fallback
        if predicted is None or expected is None:
            return ScoreResult(metric_name=self.name, score=None, details={"reason": "Missing prediction or reference"})
        is_match = (str(predicted).strip().upper() == str(expected).strip().upper())
        return ScoreResult(metric_name=self.name, score=1.0 if is_match else 0.0, passed=is_match)


class AccuracyScorer(BaseScorer):
    """Computes exact match binary accuracy for classification."""

    def __init__(self, name: str = "accuracy"):
        super().__init__(name=name)

    def score(
        self,
        predicted: Any,
        expected: Any,
        context: Optional[Dict[str, Any]] = None,
    ) -> ScoreResult:
        if predicted is None or expected is None:
            return ScoreResult(metric_name=self.name, score=None, passed=None, details={"reason": "Missing prediction or ground truth"})

        pred_str = str(predicted).strip().upper()
        exp_str = str(expected).strip().upper()
        match = (pred_str == exp_str)
        return ScoreResult(
            metric_name=self.name,
            score=1.0 if match else 0.0,
            passed=match,
            details={"predicted": pred_str, "expected": exp_str},
        )


class BrierScoreScorer(BaseScorer):
    """Computes Brier score for probabilistic binary classification.
    
    (probability - outcome)^2
    """

    def __init__(self, name: str = "brier_score"):
        super().__init__(name=name)

    def score(
        self,
        predicted: Any,
        expected: Any,
        context: Optional[Dict[str, Any]] = None,
    ) -> ScoreResult:
        ctx = context or {}
        prob = ctx.get("probability")
        if prob is None or expected is None:
            return ScoreResult(metric_name=self.name, score=None, details={"reason": "Missing probability"})

        try:
            p = float(prob)
            y = 1.0 if bool(expected) else 0.0
            brier = (p - y) ** 2
            return ScoreResult(
                metric_name=self.name,
                score=brier,
                details={"probability": p, "outcome": y},
            )
        except (ValueError, TypeError):
            return ScoreResult(metric_name=self.name, score=None, details={"reason": "Invalid probability format"})


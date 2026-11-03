"""Classification evaluation modules for Runport."""

from runport.classification.contracts import (
    CONTRACT_VERSION,
    PARITY_STATUS,
    ClassificationCase,
    HistoryStatus,
    ReviewStatus,
    Role,
    Turn,
)
from runport.classification.metrics import (
    BinaryMetrics,
    ClassificationItem,
    ClassificationMetrics,
    compute_binary_metrics,
    compute_classification_metrics,
)
from runport.classification.records import AdapterResult, PredictionRecord, PredictionStore, Task
from runport.classification.runner import ClassificationRunSummary, ClassificationRunner
from runport.classification.threshold import (
    FrozenThreshold,
    HeldOutReport,
    ProbItem,
    evaluate_at,
    evaluate_held_out,
    select_threshold_on_dev,
    sweep,
)
from runport.classification.validators import (
    ClassificationValidation,
    InvalidReason,
    validate_classification_output,
)

__all__ = [
    "CONTRACT_VERSION",
    "PARITY_STATUS",
    "ClassificationCase",
    "HistoryStatus",
    "ReviewStatus",
    "Role",
    "Turn",
    "ClassificationItem",
    "ClassificationMetrics",
    "BinaryMetrics",
    "compute_classification_metrics",
    "compute_binary_metrics",
    "AdapterResult",
    "PredictionRecord",
    "PredictionStore",
    "Task",
    "ClassificationRunSummary",
    "ClassificationRunner",
    "FrozenThreshold",
    "HeldOutReport",
    "ProbItem",
    "evaluate_at",
    "evaluate_held_out",
    "select_threshold_on_dev",
    "sweep",
    "ClassificationValidation",
    "InvalidReason",
    "validate_classification_output",
]

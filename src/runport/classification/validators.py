"""Strict output validators for classification targets."""

import json
from enum import Enum
from typing import List, Optional, Set

from pydantic import BaseModel


class InvalidReason(str, Enum):
    EMPTY_OUTPUT = "EMPTY_OUTPUT"
    UNKNOWN_LABEL = "UNKNOWN_LABEL"
    EXTRA_TEXT = "EXTRA_TEXT"
    WRONG_CASE = "WRONG_CASE"
    CODE_FENCE = "CODE_FENCE"
    INVALID_JSON = "INVALID_JSON"
    NOT_OBJECT = "NOT_OBJECT"
    MISSING_KEY = "MISSING_KEY"
    EXTRA_KEYS = "EXTRA_KEYS"
    NON_BOOLEAN = "NON_BOOLEAN"


class ClassificationValidation(BaseModel):
    valid: bool
    label: Optional[str] = None
    reason: Optional[InvalidReason] = None


def validate_classification_output(
    raw: Optional[str],
    allowed_labels: Optional[List[str]] = None,
) -> ClassificationValidation:
    """Validate a classification output against an allowed vocabulary. Case-sensitive; leading/trailing whitespace tolerated."""
    if raw is None or not raw.strip():
        return ClassificationValidation(valid=False, reason=InvalidReason.EMPTY_OUTPUT)
    text = raw.strip()
    if allowed_labels is None:
        return ClassificationValidation(valid=True, label=text)

    label_map = {l: l for l in allowed_labels}
    upper_map = {l.upper(): l for l in allowed_labels}

    if text in label_map:
        return ClassificationValidation(valid=True, label=label_map[text])
    if text.upper() in upper_map:
        return ClassificationValidation(valid=False, reason=InvalidReason.WRONG_CASE)
    if any(lbl in text.upper() for lbl in upper_map):
        return ClassificationValidation(valid=False, reason=InvalidReason.EXTRA_TEXT)
    return ClassificationValidation(valid=False, reason=InvalidReason.UNKNOWN_LABEL)

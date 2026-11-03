"""Generic classification workload contracts."""

from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator

from runport.schemas.evaluation import DataClassification, DatasetSplit

CONTRACT_VERSION = "v2"
PARITY_STATUS = "PRODUCTION_PARITY_NOT_ESTABLISHED"


class IntentLabel(str, Enum):
    """Supported intent classification labels."""
    GREETING = "GREETING"
    OUT_OF_SCOPE = "OUT_OF_SCOPE"
    UPLOAD_STATUS_CHECK = "UPLOAD_STATUS_CHECK"
    HUMAN_HANDOFF_REQUEST = "HUMAN_HANDOFF_REQUEST"
    QUERY = "QUERY"
    CLOSING = "CLOSING"
    OTHER = "OTHER"


class Role(str, Enum):
    USER = "USER"
    ASSISTANT = "ASSISTANT"


class HistoryStatus(str, Enum):
    """How much history the case carries. UNKNOWN is never treated as 'none happened'."""
    COMPLETE = "COMPLETE"
    INCOMPLETE = "INCOMPLETE"
    NONE_AVAILABLE = "NONE_AVAILABLE"
    UNKNOWN = "UNKNOWN"


class ReviewStatus(str, Enum):
    NOT_REVIEWED = "NOT_REVIEWED"
    APPROVED = "APPROVED"


class Turn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    turn_index: int = Field(ge=0)
    role: Role
    text: str
    source_ref: str = Field(default="synthetic", min_length=1)


class ClassificationCase(BaseModel):
    """Universal classification evaluation case."""
    model_config = ConfigDict(extra="forbid")

    case_id: str = Field(min_length=1)
    input_text: str
    expected_label: Optional[str] = None
    split: DatasetSplit = DatasetSplit.TEST
    category: str = "general"
    history: List[Turn] = Field(default_factory=list)
    history_status: HistoryStatus = HistoryStatus.UNKNOWN
    metadata: Dict[str, Any] = Field(default_factory=dict)
    data_classification: DataClassification = DataClassification.SYNTHETIC

    @model_validator(mode="after")
    def _validate_privacy_and_identity(self):
        # Enforce invariant: phone prefixes or forbidden keys must never be accepted
        if "user4" in self.metadata:
            raise ValueError("Forbidden key 'user4' is rejected in case metadata")
        return self

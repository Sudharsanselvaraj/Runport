"""Standard error envelope and typed HTTP exceptions for Runport REST API v1.

Specification: docs/SDK_API_CONTRACT.md section 2.4.
Enforces stable JSON error envelope:
{
    "error": {
        "code": "<stable_code>",
        "message": "<human_readable_message>",
        "details": { ... }
    }
}
"""

from __future__ import annotations

from typing import Any, Dict, Optional
from fastapi import HTTPException
from pydantic import BaseModel, Field


class ErrorDetail(BaseModel):
    code: str = Field(..., description="Stable error identifier code")
    message: str = Field(..., description="Human-readable explanation")
    details: Dict[str, Any] = Field(default_factory=dict, description="Diagnostic contextual metadata")


class ErrorEnvelope(BaseModel):
    error: ErrorDetail


class ApiV1Error(HTTPException):
    """Base class for all versioned REST API v1 errors."""

    def __init__(
        self,
        status_code: int,
        code: str,
        message: str,
        details: Optional[Dict[str, Any]] = None,
    ):
        envelope = ErrorEnvelope(
            error=ErrorDetail(
                code=code,
                message=message,
                details=details or {},
            )
        )
        super().__init__(status_code=status_code, detail=envelope.model_dump())
        self.code = code
        self.error_message = message
        self.details = details or {}


# Stable error variants according to SDK & API Contract specification


class ApprovalRequiredError(ApiV1Error):
    """428: Human approval required before live execution."""

    def __init__(self, message: str = "Human approval required before live execution.", details: Optional[Dict[str, Any]] = None):
        super().__init__(428, "approval_required", message, details)


class ApprovalInvalidError(ApiV1Error):
    """403: Invalid, expired, or non-matching approval token or fingerprint."""

    def __init__(self, message: str = "Approval token or fingerprint is invalid or has expired.", details: Optional[Dict[str, Any]] = None):
        super().__init__(403, "approval_invalid", message, details)


class PlanBlockedError(ApiV1Error):
    """409: The execution plan has preflight blockers (unresolved spend, cap reached)."""

    def __init__(self, message: str = "Plan execution is blocked.", details: Optional[Dict[str, Any]] = None):
        super().__init__(409, "plan_blocked", message, details)


class BudgetExceededApiError(ApiV1Error):
    """402: Live request would exceed budget ceiling."""

    def __init__(self, message: str = "Spend ceiling exceeded.", details: Optional[Dict[str, Any]] = None):
        super().__init__(402, "budget_exceeded", message, details)


class UnresolvedSpendApiError(ApiV1Error):
    """409: Execution is blocked fail-closed due to unresolved ledger entries."""

    def __init__(self, message: str = "Unresolved spend entries block execution.", details: Optional[Dict[str, Any]] = None):
        super().__init__(409, "unresolved_spend", message, details)


class ConfidentialityViolationApiError(ApiV1Error):
    """400: Restricted or forbidden fields detected in payload."""

    def __init__(self, message: str = "Confidentiality violation: forbidden field or secret detected.", details: Optional[Dict[str, Any]] = None):
        super().__init__(400, "confidentiality_violation", message, details)


class InvalidTargetSpecApiError(ApiV1Error):
    """400: Invalid or unresolvable target configuration."""

    def __init__(self, message: str = "Invalid target specification.", details: Optional[Dict[str, Any]] = None):
        super().__init__(400, "invalid_target_spec", message, details)


class NotFoundError(ApiV1Error):
    """404: Resource not found."""

    def __init__(self, message: str = "Requested resource not found.", details: Optional[Dict[str, Any]] = None):
        super().__init__(404, "not_found", message, details)


class UnauthorizedError(ApiV1Error):
    """401: Missing or invalid API key credentials."""

    def __init__(self, message: str = "Valid API credentials required.", details: Optional[Dict[str, Any]] = None):
        super().__init__(401, "unauthorized", message, details)


class ForbiddenError(ApiV1Error):
    """403: API key lacks required scope."""

    def __init__(self, message: str = "Insufficient permissions or missing scope.", details: Optional[Dict[str, Any]] = None):
        super().__init__(403, "forbidden", message, details)

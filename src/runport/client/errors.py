"""Runport Remote Client exception hierarchy.

Specification: docs/SDK_API_CONTRACT.md section 2.4.
"""

from typing import Any, Dict, Optional


class ClientError(Exception):
    """Base exception for all Runport client errors."""

    def __init__(self, code: str, message: str, status_code: int, details: Optional[Dict[str, Any]] = None):
        super().__init__(f"[{code}] {message}")
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details or {}


class AuthenticationError(ClientError):
    """Raised when an API key is missing or invalid (HTTP 401)."""


class PermissionDeniedError(ClientError):
    """Raised when an API key lacks required scope (HTTP 403)."""


class ApprovalRequiredError(ClientError):
    """Raised when executing an unapproved plan (HTTP 428)."""


class ApprovalInvalidError(ClientError):
    """Raised when approval fingerprint does not match or approval channel is invalid (HTTP 403)."""


class PlanBlockedError(ClientError):
    """Raised when preflight blockers prevent approval (HTTP 409)."""


class BudgetExceededError(ClientError):
    """Raised when plan or run exceeds spend cap (HTTP 402)."""


class UnresolvedSpendError(ClientError):
    """Raised when unresolved ledger entries block further live runs (HTTP 409)."""


class NotFoundError(ClientError):
    """Raised when target, dataset, plan, run, or trace is not found (HTTP 404)."""


class ConfidentialityViolationError(ClientError):
    """Raised when dataset cases violate privacy classification policy (HTTP 400)."""


class InvalidTargetSpecError(ClientError):
    """Raised when target or dataset specification is invalid (HTTP 400)."""


def raise_for_api_error(status_code: int, error_dict: Dict[str, Any]) -> None:
    """Maps API v1 error envelope to a typed ClientError."""
    code = error_dict.get("code", "unknown_error")
    msg = error_dict.get("message", "An unexpected API error occurred.")
    details = error_dict.get("details", {})

    error_map = {
        "unauthorized": AuthenticationError,
        "forbidden": PermissionDeniedError,
        "approval_required": ApprovalRequiredError,
        "approval_invalid": ApprovalInvalidError,
        "plan_blocked": PlanBlockedError,
        "budget_exceeded": BudgetExceededError,
        "unresolved_spend": UnresolvedSpendError,
        "not_found": NotFoundError,
        "confidentiality_violation": ConfidentialityViolationError,
        "invalid_target_spec": InvalidTargetSpecError,
    }

    exc_class = error_map.get(code, ClientError)
    raise exc_class(code=code, message=msg, status_code=status_code, details=details)

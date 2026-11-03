"""Execution approval models and cryptographic plan fingerprint verification.

Invariant: Non-interactive live runs without valid cryptographic approval
are refused fail-closed.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Callable, Optional
import sys

from runport.providers.base import LiveNotAuthorizedError


@dataclass(frozen=True)
class ApprovalDecision:
    """Outcome of an approval request."""

    approved: bool
    plan_fingerprint: str
    approver_kind: str
    operator: str
    reason: Optional[str] = None


class BaseApprover(ABC):
    """Abstract base class for plan execution approvers."""

    @abstractmethod
    def request_approval(
        self,
        plan_fingerprint: str,
        summary_text: str = "",
        candidate_count: int = 1,
    ) -> ApprovalDecision:
        """Request explicit operator authorization for live execution."""
        pass


class InteractiveApprover(BaseApprover):
    """Interactive approver requiring exact typed phrase verification via TTY."""

    def __init__(
        self,
        operator: str = "Operator",
        prompt_fn: Optional[Callable[[str], str]] = None,
        is_tty_fn: Optional[Callable[[], bool]] = None,
        expected_phrase_fn: Optional[Callable[[str], str]] = None,
        echo_fn: Optional[Callable[[str], None]] = None,
    ):
        self.operator = operator
        self.prompt_fn = prompt_fn or input
        self.is_tty_fn = is_tty_fn or (lambda: sys.stdin.isatty() and sys.stdout.isatty())
        self.expected_phrase_fn = expected_phrase_fn
        self.echo_fn = echo_fn

    def expected_phrase(self, plan_fingerprint: str) -> str:
        if self.expected_phrase_fn:
            return self.expected_phrase_fn(plan_fingerprint)
        return f"CONFIRM LIVE BENCHMARK {plan_fingerprint[:8].upper()}"

    def request_approval(
        self,
        plan_fingerprint: str,
        summary_text: str = "",
        candidate_count: int = 1,
    ) -> ApprovalDecision:
        if not self.is_tty_fn():
            raise LiveNotAuthorizedError(
                "Non-interactive terminal cannot provide live confirmation; live runs require interactive confirmation and are refused fail-closed."
            )

        expected = self.expected_phrase(plan_fingerprint)
        if self.echo_fn:
            if summary_text:
                for line in summary_text.splitlines():
                    self.echo_fn(line)
            self.echo_fn(f"This will send data to an external provider and may spend money. Type exactly: {expected}")
            prompt_msg = "Confirmation"
        else:
            prompt_msg = (
                f"\n[APPROVAL REQUIRED] Live run covers {candidate_count} candidates.\n"
                f"Plan Fingerprint: {plan_fingerprint}\n"
                f"To proceed, type exactly '{expected}': "
            )

        try:
            entered = self.prompt_fn(prompt_msg).strip()
        except (EOFError, KeyboardInterrupt):
            raise LiveNotAuthorizedError("Approval prompt aborted by user.")

        if entered != expected:
            raise LiveNotAuthorizedError(f"Confirmation phrase mismatch: expected '{expected}', got '{entered}'.")

        return ApprovalDecision(
            approved=True,
            plan_fingerprint=plan_fingerprint,
            approver_kind="INTERACTIVE",
            operator=self.operator,
        )


class TokenApprover(BaseApprover):
    """CI/Automation approver validating a pre-generated plan fingerprint token.

    Valid ONLY if enabled=True and token matches the freshly recomputed plan.
    Enforces single-use: once consumed, cannot be reused.
    """

    def __init__(
        self,
        token: str,
        enabled: bool = False,
        operator: str = "CI-Automation",
    ):
        self.token = token.strip()
        self.enabled = enabled
        self.operator = operator
        self._consumed = False

    def request_approval(
        self,
        plan_fingerprint: str,
        summary_text: str = "",
        candidate_count: int = 1,
    ) -> ApprovalDecision:
        if not self.enabled:
            raise LiveNotAuthorizedError("Token approver is disabled by policy in workspace configuration; live run refused.")

        if self._consumed:
            raise LiveNotAuthorizedError("Approval token has already been consumed; cannot be reused.")

        if not plan_fingerprint:
            raise LiveNotAuthorizedError("Approve token provided but no plan fingerprint was computed.")

        if not self.token or self.token != plan_fingerprint.strip():
            raise LiveNotAuthorizedError(
                f"Approval token mismatch: provided token '{self.token}' does not match recomputed plan fingerprint '{plan_fingerprint}'; run refused."
            )

        self._consumed = True
        return ApprovalDecision(
            approved=True,
            plan_fingerprint=plan_fingerprint,
            approver_kind="TOKEN",
            operator=self.operator,
        )


class ModalApprover(BaseApprover):
    """Web UI modal approval verifying matching fingerprint payload."""

    def __init__(
        self,
        confirmed_fingerprint: str,
        operator: str = "Web User",
    ):
        self.confirmed_fingerprint = confirmed_fingerprint.strip()
        self.operator = operator

    def request_approval(
        self,
        plan_fingerprint: str,
        summary_text: str = "",
        candidate_count: int = 1,
    ) -> ApprovalDecision:
        if self.confirmed_fingerprint != plan_fingerprint:
            raise LiveNotAuthorizedError(
                f"Web confirmation mismatch: approved fingerprint '{self.confirmed_fingerprint}' does not match plan '{plan_fingerprint}'."
            )

        return ApprovalDecision(
            approved=True,
            plan_fingerprint=plan_fingerprint,
            approver_kind="MODAL",
            operator=self.operator,
        )

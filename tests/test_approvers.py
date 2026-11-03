"""Unit tests for approval mechanisms (Interactive, Token, Modal)."""

import pytest
from runport.core.approvers import InteractiveApprover, ModalApprover, TokenApprover
from runport.providers.base import LiveNotAuthorizedError


def test_interactive_approver_success_and_failures():
    """InteractiveApprover requires TTY and exact typed confirmation phrase."""
    fingerprint = "0123456789abcdef0123456789abcdef"
    expected = "CONFIRM LIVE BENCHMARK 01234567"

    # Non-TTY rejected fail-closed
    approver_no_tty = InteractiveApprover(is_tty_fn=lambda: False)
    with pytest.raises(LiveNotAuthorizedError, match="Non-interactive terminal"):
        approver_no_tty.request_approval(fingerprint)

    # TTY with mismatch rejected
    approver_mismatch = InteractiveApprover(prompt_fn=lambda _: "CONFIRM WRONG", is_tty_fn=lambda: True)
    with pytest.raises(LiveNotAuthorizedError, match="phrase mismatch"):
        approver_mismatch.request_approval(fingerprint)

    # TTY with exact match approved
    approver_ok = InteractiveApprover(prompt_fn=lambda _: expected, is_tty_fn=lambda: True)
    decision = approver_ok.request_approval(fingerprint)
    assert decision.approved is True
    assert decision.plan_fingerprint == fingerprint
    assert decision.approver_kind == "INTERACTIVE"


def test_token_approver_policy_and_fingerprint_matching():
    """TokenApprover is disabled by default; when enabled, requires exact fingerprint match."""
    fp = "abcd1234efgh5678"

    # Disabled by default
    approver_disabled = TokenApprover(token=fp, enabled=False)
    with pytest.raises(LiveNotAuthorizedError, match="disabled by policy"):
        approver_disabled.request_approval(fp)

    # Enabled with token mismatch rejected
    approver_bad_token = TokenApprover(token="stale-or-wrong-token", enabled=True)
    with pytest.raises(LiveNotAuthorizedError, match="token mismatch"):
        approver_bad_token.request_approval(fp)

    # Enabled with exact match succeeds
    approver_ok = TokenApprover(token=fp, enabled=True)
    decision = approver_ok.request_approval(fp)
    assert decision.approved is True
    assert decision.approver_kind == "TOKEN"


def test_modal_approver_verification():
    """ModalApprover verifies web payload fingerprint match."""
    fp = "modal-fp-12345"

    approver_bad = ModalApprover(confirmed_fingerprint="mismatched-fp")
    with pytest.raises(LiveNotAuthorizedError, match="confirmation mismatch"):
        approver_bad.request_approval(fp)

    approver_ok = ModalApprover(confirmed_fingerprint=fp)
    decision = approver_ok.request_approval(fp)
    assert decision.approved is True
    assert decision.approver_kind == "MODAL"


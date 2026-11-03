"""Fail-closed confirmation for live (outbound API) runs.

A live run needs an explicit, typed confirmation from an interactive terminal. Piped or
otherwise non-interactive execution can never confirm, so it can never reach a provider.
"""

import sys
from dataclasses import dataclass
from typing import Callable, Optional, Sequence, Tuple

from runport.providers.base import LiveNotAuthorizedError

CONFIRM_PREFIX = "RUN LIVE"


@dataclass(frozen=True)
class LiveAuthorization:
    """Proof that a human confirmed a live run for specific models. Created only by `confirm_live_run`."""
    models: Tuple[str, ...]

    def covers(self, model_id: str) -> bool:
        return model_id in self.models


def expected_phrase(models: Sequence[str], plan_fingerprint: Optional[str] = None) -> str:
    """Typed confirmation text. When a plan fingerprint is given, approval is bound to that exact plan."""
    base = f"{CONFIRM_PREFIX} {', '.join(models)}"
    return f"{base} PLAN {plan_fingerprint}" if plan_fingerprint else base


def confirm_live_run(
    models: Sequence[str],
    summary_lines: Sequence[str] = (),
    *,
    is_interactive: Optional[Callable[[], bool]] = None,
    prompt: Optional[Callable[[str], str]] = None,
    echo: Callable[[str], None] = print,
    plan_fingerprint: Optional[str] = None,
    approve_token: Optional[str] = None,
) -> LiveAuthorization:
    """Return a LiveAuthorization only if:
    1. In CI / automated environments: `approve_token` matches the freshly recomputed `plan_fingerprint`.
    2. In interactive terminals: an operator types the exact confirmation phrase.

    Thin wrapper delegating directly to unified TokenApprover or InteractiveApprover.
    Raises LiveNotAuthorizedError otherwise. Nothing here contacts any provider.
    """
    if not models or any(not m for m in models):
        raise LiveNotAuthorizedError("Live run needs at least one explicit model id")

    if approve_token is not None:
        from runport.core.approvers import TokenApprover
        token_approver = TokenApprover(token=approve_token, enabled=True)
        token_approver.request_approval(plan_fingerprint=plan_fingerprint or "")
        return LiveAuthorization(models=tuple(models))

    from runport.core.approvers import InteractiveApprover
    phrase = expected_phrase(models, plan_fingerprint)
    summary_text = "\n".join(summary_lines)
    approver = InteractiveApprover(
        prompt_fn=prompt,
        is_tty_fn=is_interactive,
        expected_phrase_fn=lambda fp: phrase,
        echo_fn=echo,
    )
    approver.request_approval(
        plan_fingerprint=plan_fingerprint or "MANUAL",
        summary_text=summary_text,
        candidate_count=len(models),
    )
    return LiveAuthorization(models=tuple(models))


def require_live_authorization(auth: Optional[LiveAuthorization], model_id: str) -> None:
    """Defence in depth for programmatic callers: a live run needs an authorization covering the model."""
    if auth is None or not auth.covers(model_id):
        raise LiveNotAuthorizedError(f"No live authorization covers model '{model_id}'; live run refused.")

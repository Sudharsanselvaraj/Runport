"""Persisted, cross-process approval lifecycle for live execution plans.

A live plan moves PENDING -> APPROVED -> CONSUMED. Each transition is one conditional UPDATE in SQLite, so it is
atomic across threads and processes: two concurrent executions of the same approval cannot both succeed.

* Requesting a plan and approving it are separate operations. ``approve`` accepts only human or operator-held
  channels (interactive CLI, the local Web UI, a CI token). The MCP server and SDK can request approval but have
  no channel that approves.
* Approvals expire. A pending plan that nobody approves, or an approval that is not used, stops being valid.
* Approval binds to the plan fingerprint; execution re-derives the fingerprint from the current inputs and refuses
  a mismatch, so a changed target, dataset or cap invalidates the approval.
"""

from __future__ import annotations

import json
import secrets
import time
from dataclasses import dataclass
from typing import Any, Dict, Optional

from runport.providers.base import LiveNotAuthorizedError
from runport.storage.db import DatabaseManager

PENDING = "PENDING"
APPROVED = "APPROVED"
CONSUMED = "CONSUMED"

# Channels through which a person (or an operator-held CI secret) approves spend. "mcp" and "sdk" are absent on purpose.
APPROVAL_CHANNELS = frozenset({"cli_interactive", "web_ui", "ci_token"})

DEFAULT_PENDING_TTL_S = 15 * 60
DEFAULT_APPROVED_TTL_S = 15 * 60

_SCHEMA = """
CREATE TABLE IF NOT EXISTS plan_approvals (
    plan_id TEXT PRIMARY KEY,
    fingerprint TEXT NOT NULL,
    summary_json TEXT NOT NULL,
    status TEXT NOT NULL,
    requested_by TEXT NOT NULL,
    created_at REAL NOT NULL,
    expires_at REAL NOT NULL,
    approved_by TEXT,
    approved_at REAL,
    consumed_at REAL
);
CREATE INDEX IF NOT EXISTS idx_plan_approvals_fingerprint ON plan_approvals(fingerprint);
"""


class ApprovalError(LiveNotAuthorizedError):
    """An approval is missing, expired, already used, or does not match the plan."""


@dataclass(frozen=True)
class ApprovalRecord:
    plan_id: str
    fingerprint: str
    summary: Dict[str, Any]
    status: str
    requested_by: str
    created_at: float
    expires_at: float
    approved_by: Optional[str]
    approved_at: Optional[float]
    consumed_at: Optional[float]

    def is_expired(self, now: Optional[float] = None) -> bool:
        return (now if now is not None else time.time()) >= self.expires_at


class ApprovalStore:
    def __init__(self, db: Optional[DatabaseManager] = None, clock=time.time) -> None:
        self.db = db or DatabaseManager()
        self._clock = clock
        self.db.init_db()
        with self.db.get_connection() as conn:
            conn.executescript(_SCHEMA)
            conn.commit()

    def register(self, fingerprint: str, summary: Dict[str, Any], requested_by: str, ttl_s: float = DEFAULT_PENDING_TTL_S) -> ApprovalRecord:
        now = self._clock()
        plan_id = f"plan-{secrets.token_hex(8)}"
        with self.db.get_connection() as conn:
            conn.execute(
                "INSERT INTO plan_approvals (plan_id, fingerprint, summary_json, status, requested_by, created_at, expires_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (plan_id, fingerprint, json.dumps(summary, sort_keys=True, default=str), PENDING, requested_by, now, now + ttl_s),
            )
            conn.commit()
        record = self.get(plan_id)
        assert record is not None
        return record

    def get(self, plan_id: str) -> Optional[ApprovalRecord]:
        with self.db.get_connection() as conn:
            row = conn.execute("SELECT * FROM plan_approvals WHERE plan_id = ?", (plan_id,)).fetchone()
        return _row(row) if row else None

    def find_by_fingerprint(self, fingerprint: str) -> Optional[ApprovalRecord]:
        """Most recent plan with this fingerprint (fingerprints include a per-plan nonce, so they are unique in practice)."""
        with self.db.get_connection() as conn:
            row = conn.execute("SELECT * FROM plan_approvals WHERE fingerprint = ? ORDER BY created_at DESC LIMIT 1", (fingerprint,)).fetchone()
        return _row(row) if row else None

    def approve(self, plan_id: str, fingerprint: str, channel: str, approver: str, ttl_s: float = DEFAULT_APPROVED_TTL_S) -> ApprovalRecord:
        if channel not in APPROVAL_CHANNELS:
            raise ApprovalError(f"Channel '{channel}' cannot approve live spend; a person must approve through the CLI, the Web UI or a CI token.")
        now = self._clock()
        with self.db.get_connection() as conn:
            cur = conn.execute(
                "UPDATE plan_approvals SET status = ?, approved_by = ?, approved_at = ?, expires_at = ? "
                "WHERE plan_id = ? AND fingerprint = ? AND status = ? AND expires_at > ?",
                (APPROVED, f"{channel}:{approver}", now, now + ttl_s, plan_id, fingerprint, PENDING, now),
            )
            conn.commit()
            changed = cur.rowcount
        if changed != 1:
            raise ApprovalError(self._why_not(plan_id, fingerprint, expected=PENDING))
        record = self.get(plan_id)
        assert record is not None
        return record

    def consume(self, plan_id: str, fingerprint: str) -> ApprovalRecord:
        """Atomically marks an approved plan used. Exactly one caller can succeed."""
        now = self._clock()
        with self.db.get_connection() as conn:
            cur = conn.execute(
                "UPDATE plan_approvals SET status = ?, consumed_at = ? WHERE plan_id = ? AND fingerprint = ? AND status = ? AND expires_at > ?",
                (CONSUMED, now, plan_id, fingerprint, APPROVED, now),
            )
            conn.commit()
            changed = cur.rowcount
        if changed != 1:
            raise ApprovalError(self._why_not(plan_id, fingerprint, expected=APPROVED))
        record = self.get(plan_id)
        assert record is not None
        return record

    def _why_not(self, plan_id: str, fingerprint: str, expected: str) -> str:
        rec = self.get(plan_id)
        if rec is None:
            return f"No plan '{plan_id}' exists; nothing was approved or sent."
        if rec.fingerprint != fingerprint:
            return "Plan fingerprint does not match the approved plan (the target, dataset or cap changed); approval refused."
        if rec.status == CONSUMED:
            return "This approval has already been used; it cannot be reused."
        if rec.is_expired(self._clock()):
            return f"Plan '{plan_id}' expired before it was {'approved' if expected == PENDING else 'used'}; create a new plan."
        if expected == APPROVED and rec.status == PENDING:
            return f"Plan '{plan_id}' has not been approved by a person yet."
        return f"Plan '{plan_id}' is {rec.status}, expected {expected}."


def _row(row: Any) -> ApprovalRecord:
    return ApprovalRecord(
        plan_id=row["plan_id"],
        fingerprint=row["fingerprint"],
        summary=json.loads(row["summary_json"]),
        status=row["status"],
        requested_by=row["requested_by"],
        created_at=row["created_at"],
        expires_at=row["expires_at"],
        approved_by=row["approved_by"],
        approved_at=row["approved_at"],
        consumed_at=row["consumed_at"],
    )

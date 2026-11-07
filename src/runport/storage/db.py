"""SQLite database initialization, migration, and transactional persistence."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import TYPE_CHECKING, List, Optional, Dict, Any

from runport.core.config import settings

if TYPE_CHECKING:
    from runport.traces.domain import (
        Span,
        SpanEvent,
        SpanKind,
        SpanStatus,
        Trace,
    )


def _to_utc_dt(val: Any) -> Optional[datetime]:
    """Helper to convert datetime or ISO string to UTC datetime."""
    if val is None:
        return None
    if isinstance(val, str):
        val = datetime.fromisoformat(val.replace("Z", "+00:00"))
    if isinstance(val, datetime):
        if val.tzinfo is None:
            return val.replace(tzinfo=timezone.utc)
        return val.astimezone(timezone.utc)
    raise ValueError(f"Cannot parse UTC datetime from {type(val)}: {val}")


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS budget_ledger (
    transaction_id TEXT PRIMARY KEY,
    timestamp TEXT NOT NULL,
    run_id TEXT,
    model_id TEXT NOT NULL,
    provider TEXT NOT NULL,
    amount_micros INTEGER NOT NULL,
    amount_usd TEXT NOT NULL,
    is_pilot INTEGER NOT NULL DEFAULT 1,
    is_preflight_estimate INTEGER NOT NULL DEFAULT 0,
    is_simulated INTEGER NOT NULL DEFAULT 0,
    is_unresolved INTEGER NOT NULL DEFAULT 0,
    cost_basis TEXT NOT NULL DEFAULT 'UNSPECIFIED',
    description TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS model_portfolio (
    model_id TEXT PRIMARY KEY,
    display_name TEXT NOT NULL,
    provider TEXT NOT NULL,
    deployment_mode TEXT NOT NULL,
    license TEXT NOT NULL,
    context_length INTEGER,
    input_price_per_1m_usd TEXT NOT NULL,
    output_price_per_1m_usd TEXT NOT NULL,
    verification_status TEXT NOT NULL,
    experimental_purpose TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS evaluation_runs (
    run_id TEXT PRIMARY KEY,
    timestamp TEXT NOT NULL,
    model_id TEXT NOT NULL,
    dataset_path TEXT NOT NULL,
    total_cases INTEGER NOT NULL,
    completed_cases INTEGER NOT NULL,
    failed_cases INTEGER NOT NULL,
    total_cost_usd TEXT NOT NULL,
    mean_latency_ms REAL,
    mean_accuracy REAL,
    mean_groundedness REAL,
    mean_overall_score REAL,
    is_dry_run INTEGER NOT NULL DEFAULT 1,
    notes TEXT
);

CREATE TABLE IF NOT EXISTS evaluation_results (
    result_id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL,
    case_id TEXT NOT NULL,
    prompt TEXT NOT NULL,
    expected_answer TEXT,
    generated_output TEXT NOT NULL,
    latency_ms REAL,
    prompt_tokens INTEGER,
    completion_tokens INTEGER,
    cost_usd TEXT,
    accuracy REAL,
    groundedness REAL,
    format_adherence REAL,
    overall_score REAL,
    evaluator_notes TEXT,
    score_kind TEXT,
    evaluator TEXT,
    FOREIGN KEY (run_id) REFERENCES evaluation_runs(run_id)
);

CREATE TABLE IF NOT EXISTS budget_reservations (
    reservation_id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL,
    amount_micros INTEGER NOT NULL,
    is_pilot INTEGER NOT NULL DEFAULT 1,
    created_at REAL NOT NULL,
    expires_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS schema_migrations (
    version INTEGER PRIMARY KEY,
    applied_at TEXT NOT NULL,
    description TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS traces (
    trace_id TEXT PRIMARY KEY,
    run_id TEXT,
    case_id TEXT,
    target_id TEXT,
    session_id TEXT,
    name TEXT NOT NULL,
    status TEXT NOT NULL,
    start_time TEXT,
    end_time TEXT,
    attributes_json TEXT NOT NULL DEFAULT '{}',
    schema_version INTEGER NOT NULL DEFAULT 1,
    source TEXT NOT NULL DEFAULT 'native',
    source_ref TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY (run_id) REFERENCES evaluation_runs(run_id)
);

CREATE TABLE IF NOT EXISTS spans (
    trace_id TEXT NOT NULL,
    span_id TEXT NOT NULL,
    parent_span_id TEXT,
    name TEXT NOT NULL,
    kind TEXT NOT NULL,
    status TEXT NOT NULL,
    start_time TEXT,
    end_time TEXT,
    duration_ms REAL,
    provider TEXT,
    model TEXT,
    prompt_tokens INTEGER,
    completion_tokens INTEGER,
    total_tokens INTEGER,
    cost_usd TEXT,
    cost_basis TEXT,
    attributes_json TEXT NOT NULL DEFAULT '{}',
    events_json TEXT NOT NULL DEFAULT '[]',
    error_json TEXT,
    attempt INTEGER NOT NULL DEFAULT 1,
    source TEXT NOT NULL DEFAULT 'native',
    created_at TEXT NOT NULL,
    PRIMARY KEY (trace_id, span_id),
    FOREIGN KEY (trace_id) REFERENCES traces(trace_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_traces_run_id ON traces(run_id);
CREATE INDEX IF NOT EXISTS idx_traces_run_case ON traces(run_id, case_id);
CREATE INDEX IF NOT EXISTS idx_traces_status ON traces(status);
CREATE INDEX IF NOT EXISTS idx_traces_start_time ON traces(start_time);
CREATE INDEX IF NOT EXISTS idx_spans_trace ON spans(trace_id);
CREATE INDEX IF NOT EXISTS idx_spans_parent ON spans(trace_id, parent_span_id);
CREATE INDEX IF NOT EXISTS idx_spans_kind ON spans(trace_id, kind);
CREATE INDEX IF NOT EXISTS idx_spans_status ON spans(status);
CREATE INDEX IF NOT EXISTS idx_spans_start_time ON spans(start_time);

"""


class DatabaseManager:
    """Manages SQLite connections, idempotent schemas, and budget ledger records."""

    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = Path(db_path) if db_path is not None else settings.db_path

    def get_connection(self) -> sqlite3.Connection:
        """Opens a connection with WAL mode and row factory."""
        if str(self.db_path) != ":memory:":
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        if str(self.db_path) != ":memory:":
            conn.execute("PRAGMA journal_mode = WAL;")
        conn.execute("PRAGMA foreign_keys = ON;")
        return conn

    def init_db(self) -> None:
        """Idempotently initializes tables and runs additive migrations."""
        with self.get_connection() as conn:
            conn.executescript(SCHEMA_SQL)
            self._migrate_ledger(conn)
            self._migrate_evaluation_results(conn)
            self._migrate_score_provenance(conn)
            conn.commit()
            self._migrate_evaluation_runs(conn)
            self._migrate_canonical_traces(conn)

    @staticmethod
    def _migrate_evaluation_runs(conn: sqlite3.Connection) -> None:
        """Allow NULL run-level means ('Null is not 0'): an unmeasured mean must not be stored as 0.

        Rebuilds the table without NOT NULL on the mean columns. Foreign keys are switched off for the
        rebuild (outside any transaction, as SQLite requires) so evaluation_results keeps its references.
        """
        cols = {r[1]: bool(r[3]) for r in conn.execute("PRAGMA table_info(evaluation_runs)").fetchall()}
        if not cols or not any(cols.get(c, False) for c in ("mean_latency_ms", "mean_accuracy", "mean_groundedness", "mean_overall_score")):
            return
        conn.commit()
        conn.execute("PRAGMA foreign_keys = OFF")
        try:
            conn.execute("BEGIN")
            conn.execute("""
                CREATE TABLE evaluation_runs_new (
                    run_id TEXT PRIMARY KEY,
                    timestamp TEXT NOT NULL,
                    model_id TEXT NOT NULL,
                    dataset_path TEXT NOT NULL,
                    total_cases INTEGER NOT NULL,
                    completed_cases INTEGER NOT NULL,
                    failed_cases INTEGER NOT NULL,
                    total_cost_usd TEXT NOT NULL,
                    mean_latency_ms REAL,
                    mean_accuracy REAL,
                    mean_groundedness REAL,
                    mean_overall_score REAL,
                    is_dry_run INTEGER NOT NULL DEFAULT 1,
                    notes TEXT
                )
            """)
            conn.execute("""
                INSERT INTO evaluation_runs_new SELECT
                    run_id, timestamp, model_id, dataset_path, total_cases, completed_cases, failed_cases,
                    total_cost_usd, mean_latency_ms, mean_accuracy, mean_groundedness, mean_overall_score,
                    is_dry_run, notes
                FROM evaluation_runs
            """)
            conn.execute("DROP TABLE evaluation_runs")
            conn.execute("ALTER TABLE evaluation_runs_new RENAME TO evaluation_runs")
            conn.execute(
                "INSERT OR IGNORE INTO schema_migrations (version, applied_at, description) "
                "VALUES (3, datetime('now'), 'Make run-level mean columns in evaluation_runs nullable')"
            )
            conn.execute("COMMIT")
        except Exception:
            conn.execute("ROLLBACK")
            raise
        finally:
            conn.execute("PRAGMA foreign_keys = ON")

    @staticmethod
    def _migrate_evaluation_results(conn: sqlite3.Connection) -> None:
        """Ensure columns in evaluation_results allow NULL to respect 'Null is not 0' invariant."""
        cur = conn.execute("PRAGMA table_info(evaluation_results)")
        res_cols = {r[1]: bool(r[3]) for r in cur.fetchall()}  # col_name -> notnull
        if res_cols and (res_cols.get("accuracy", False) or res_cols.get("prompt_tokens", False)):
            conn.execute("ALTER TABLE evaluation_results RENAME TO _legacy_evaluation_results")
            conn.execute("""
                CREATE TABLE evaluation_results (
                    result_id TEXT PRIMARY KEY,
                    run_id TEXT NOT NULL,
                    case_id TEXT NOT NULL,
                    prompt TEXT NOT NULL,
                    expected_answer TEXT,
                    generated_output TEXT NOT NULL,
                    latency_ms REAL,
                    prompt_tokens INTEGER,
                    completion_tokens INTEGER,
                    cost_usd TEXT,
                    accuracy REAL,
                    groundedness REAL,
                    format_adherence REAL,
                    overall_score REAL,
                    evaluator_notes TEXT,
                    FOREIGN KEY (run_id) REFERENCES evaluation_runs(run_id)
                )
            """)
            conn.execute("""
                INSERT INTO evaluation_results SELECT
                    result_id, run_id, case_id, prompt, expected_answer,
                    generated_output, latency_ms, prompt_tokens, completion_tokens,
                    cost_usd, accuracy, groundedness, format_adherence, overall_score,
                    evaluator_notes
                FROM _legacy_evaluation_results
            """)
            conn.execute("DROP TABLE _legacy_evaluation_results")
            conn.execute(
                "INSERT OR IGNORE INTO schema_migrations (version, applied_at, description) "
                "VALUES (2, datetime('now'), 'Make accuracy, tokens, and cost columns in evaluation_results nullable')"
            )

    @staticmethod
    def _migrate_score_provenance(conn: sqlite3.Connection) -> None:
        """Add score provenance columns. Rows written before them keep NULL: their kind is unknown, not ground truth."""
        cols = {r[1] for r in conn.execute("PRAGMA table_info(evaluation_results)").fetchall()}
        if cols and "score_kind" not in cols:
            conn.execute("ALTER TABLE evaluation_results ADD COLUMN score_kind TEXT")
        if cols and "evaluator" not in cols:
            conn.execute("ALTER TABLE evaluation_results ADD COLUMN evaluator TEXT")

    @staticmethod
    def _migrate_ledger(conn: sqlite3.Connection) -> None:
        """Separate simulated from actual spend in ledgers created before the column existed.

        Legacy rows are marked simulated ONLY when the run they belong to is recorded as a dry run (evaluation_runs.is_dry_run = 1).
        Rows with no such evidence stay counted as actual, which is the conservative choice for a spend ceiling.
        """
        cols = [r[1] for r in conn.execute("PRAGMA table_info(budget_ledger)").fetchall()]
        if "is_simulated" not in cols:
            conn.execute("ALTER TABLE budget_ledger ADD COLUMN is_simulated INTEGER NOT NULL DEFAULT 0")
        if "is_unresolved" not in cols:
            conn.execute("ALTER TABLE budget_ledger ADD COLUMN is_unresolved INTEGER NOT NULL DEFAULT 0")
        if "cost_basis" not in cols:
            conn.execute("ALTER TABLE budget_ledger ADD COLUMN cost_basis TEXT NOT NULL DEFAULT 'UNSPECIFIED'")
        conn.execute("UPDATE budget_ledger SET is_simulated = 1 WHERE is_simulated = 0 AND run_id IN (SELECT run_id FROM evaluation_runs WHERE is_dry_run = 1)")
        conn.execute(
            "INSERT OR IGNORE INTO schema_migrations (version, applied_at, description) "
            "VALUES (1, datetime('now'), 'Base schema with ledger simulation and unresolved spend columns')"
        )

    @staticmethod
    def _migrate_canonical_traces(conn: sqlite3.Connection) -> None:
        """Additive migration 4: Ensure canonical traces and spans tables and indexes exist.

        Preserves all existing tables and data. Safe for existing user databases.
        """
        tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
        if "traces" not in tables:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS traces (
                    trace_id TEXT PRIMARY KEY,
                    run_id TEXT,
                    case_id TEXT,
                    target_id TEXT,
                    session_id TEXT,
                    name TEXT NOT NULL,
                    status TEXT NOT NULL,
                    start_time TEXT,
                    end_time TEXT,
                    attributes_json TEXT NOT NULL DEFAULT '{}',
                    schema_version INTEGER NOT NULL DEFAULT 1,
                    source TEXT NOT NULL DEFAULT 'native',
                    source_ref TEXT,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (run_id) REFERENCES evaluation_runs(run_id)
                )
            """)
        if "spans" not in tables:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS spans (
                    trace_id TEXT NOT NULL,
                    span_id TEXT NOT NULL,
                    parent_span_id TEXT,
                    name TEXT NOT NULL,
                    kind TEXT NOT NULL,
                    status TEXT NOT NULL,
                    start_time TEXT,
                    end_time TEXT,
                    duration_ms REAL,
                    provider TEXT,
                    model TEXT,
                    prompt_tokens INTEGER,
                    completion_tokens INTEGER,
                    total_tokens INTEGER,
                    cost_usd TEXT,
                    cost_basis TEXT,
                    attributes_json TEXT NOT NULL DEFAULT '{}',
                    events_json TEXT NOT NULL DEFAULT '[]',
                    error_json TEXT,
                    attempt INTEGER NOT NULL DEFAULT 1,
                    source TEXT NOT NULL DEFAULT 'native',
                    created_at TEXT NOT NULL,
                    PRIMARY KEY (trace_id, span_id),
                    FOREIGN KEY (trace_id) REFERENCES traces(trace_id) ON DELETE CASCADE
                )
            """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_traces_run_id ON traces(run_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_traces_run_case ON traces(run_id, case_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_traces_status ON traces(status)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_traces_start_time ON traces(start_time)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_spans_trace ON spans(trace_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_spans_parent ON spans(trace_id, parent_span_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_spans_kind ON spans(trace_id, kind)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_spans_status ON spans(status)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_spans_start_time ON spans(start_time)")
        conn.execute(
            "INSERT OR IGNORE INTO schema_migrations (version, applied_at, description) "
            "VALUES (4, datetime('now'), 'Add canonical traces and spans tables and indexes')"
        )
        conn.commit()

    def record_transaction(
        self,
        transaction_id: str,
        model_id: str,
        provider: str,
        amount_usd: Decimal,
        description: str,
        run_id: Optional[str] = None,
        is_pilot: bool = True,
        is_preflight_estimate: bool = False,
        timestamp: Optional[str] = None,
        is_simulated: bool = False,
        is_unresolved: bool = False,
        cost_basis: str = "UNSPECIFIED",
    ) -> None:
        """Records a new entry in the budget ledger using exact integer micros and Decimal string."""
        if timestamp is None:
            timestamp = datetime.now(timezone.utc).isoformat()

        amount_micros = int(amount_usd * 1_000_000)
        formatted_usd = f"{amount_usd:.6f}"

        with self.get_connection() as conn:
            conn.execute(
                """
                INSERT INTO budget_ledger (
                    transaction_id, timestamp, run_id, model_id, provider,
                    amount_micros, amount_usd, is_pilot, is_preflight_estimate, is_simulated, is_unresolved, cost_basis, description
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    transaction_id,
                    timestamp,
                    run_id,
                    model_id,
                    provider,
                    amount_micros,
                    formatted_usd,
                    1 if is_pilot else 0,
                    1 if is_preflight_estimate else 0,
                    1 if is_simulated else 0,
                    1 if is_unresolved else 0,
                    cost_basis,
                    description,
                ),
            )
            conn.commit()

    def get_cumulative_spend(self, include_estimates: bool = False) -> tuple[int, Decimal]:
        """Returns total historical spend as (micros, Decimal)."""
        with self.get_connection() as conn:
            where_clause = "WHERE is_simulated = 0" + ("" if include_estimates else " AND is_preflight_estimate = 0")
            cursor = conn.execute(f"SELECT COALESCE(SUM(amount_micros), 0) FROM budget_ledger {where_clause}")
            row = cursor.fetchone()
            micros = row[0] if row else 0
            return micros, Decimal(micros) / Decimal("1000000")

    def purge_simulated(self, backup: bool = True) -> Dict[str, Any]:
        """Remove every simulated ledger row and every stored dry-run run/result. A copy of the database is made first.

        Rows that are not simulated (live, estimated-by-a-real-request, unresolved, reconciled) are never touched.
        """
        import shutil

        self.init_db()
        backup_path = None
        if backup and str(self.db_path) != ":memory:" and Path(self.db_path).exists():
            backup_path = Path(f"{self.db_path}.bak-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}")
            shutil.copy2(self.db_path, backup_path)
        with self.get_connection() as conn:
            dry_ids = [r[0] for r in conn.execute("SELECT run_id FROM evaluation_runs WHERE is_dry_run = 1").fetchall()]
            ledger = conn.execute("DELETE FROM budget_ledger WHERE is_simulated = 1").rowcount
            results = 0
            for rid in dry_ids:
                results += conn.execute("DELETE FROM evaluation_results WHERE run_id = ?", (rid,)).rowcount
            runs = conn.execute("DELETE FROM evaluation_runs WHERE is_dry_run = 1").rowcount
            conn.commit()
        return {"ledger_rows": ledger, "runs": runs, "results": results, "backup": str(backup_path) if backup_path else None}

    def get_unresolved(self) -> List[Dict[str, Any]]:
        """Ledger entries for requests that may have been billed but whose cost is unknown. Amount is never invented."""
        with self.get_connection() as conn:
            cur = conn.execute(
                "SELECT transaction_id, timestamp, run_id, model_id, provider, description FROM budget_ledger WHERE is_unresolved = 1 ORDER BY timestamp"
            )
            return [dict(r) for r in cur.fetchall()]

    def reconcile_transaction(self, transaction_id: str, amount_usd: Decimal, note: str = "") -> None:
        """Resolve an unresolved entry with an amount the operator read from the provider dashboard (recorded as RECONCILED_MANUAL)."""
        with self.get_connection() as conn:
            row = conn.execute("SELECT is_unresolved FROM budget_ledger WHERE transaction_id = ?", (transaction_id,)).fetchone()
            if row is None:
                raise KeyError(f"No ledger entry {transaction_id}")
            if not row[0]:
                raise ValueError(f"Ledger entry {transaction_id} is not unresolved")
            conn.execute(
                "UPDATE budget_ledger SET is_unresolved = 0, amount_micros = ?, amount_usd = ?, cost_basis = 'RECONCILED_MANUAL', "
                "description = description || ?  WHERE transaction_id = ?",
                (int(amount_usd * 1_000_000), f"{amount_usd:.6f}", f" [reconciled manually: {note or 'amount from provider dashboard'}]", transaction_id),
            )
            conn.commit()

    def get_spend_by_basis(self) -> Dict[str, Decimal]:
        """Actual-side spend grouped by how the cost was established (simulated and pre-run estimates excluded)."""
        with self.get_connection() as conn:
            cur = conn.execute(
                "SELECT cost_basis, COALESCE(SUM(amount_micros), 0) FROM budget_ledger WHERE is_simulated = 0 AND is_preflight_estimate = 0 AND is_unresolved = 0 GROUP BY cost_basis"
            )
            return {b: Decimal(m) / Decimal("1000000") for b, m in cur.fetchall()}

    def get_simulated_spend(self) -> tuple[int, Decimal]:
        """Returns spend recorded by dry-run simulations. It never counts against any ceiling."""
        with self.get_connection() as conn:
            row = conn.execute("SELECT COALESCE(SUM(amount_micros), 0) FROM budget_ledger WHERE is_simulated = 1").fetchone()
            micros = row[0] if row else 0
            return micros, Decimal(micros) / Decimal("1000000")

    def reserve_budget(
        self,
        reservation_id: str,
        run_id: str,
        amount_usd: Decimal,
        *,
        is_pilot: bool,
        total_cap_usd: Decimal,
        pilot_cap_usd: Decimal,
        run_cap_usd: Decimal,
        ttl_s: float = 1800.0,
    ) -> Optional[str]:
        """Atomically reserve worst-case spend for one case. Returns None on success, or the reason it was refused.

        One `BEGIN IMMEDIATE` transaction reads booked spend plus every open reservation and inserts the new one, so two
        concurrent runs cannot both pass a ceiling that only one of them fits under. Booked spend excludes simulated rows
        and pre-run estimates (as everywhere else); reservations expire so a crashed process cannot hold budget forever.
        """
        import time as _time

        amount = int((Decimal(amount_usd) * Decimal("1000000")).to_integral_value())
        now = _time.time()
        conn = sqlite3.connect(str(self.db_path), timeout=30.0, isolation_level=None)
        try:
            conn.execute("PRAGMA journal_mode = WAL;") if str(self.db_path) != ":memory:" else None
            conn.execute("BEGIN IMMEDIATE")
            conn.execute("DELETE FROM budget_reservations WHERE expires_at <= ?", (now,))
            if conn.execute("SELECT COUNT(*) FROM budget_ledger WHERE is_unresolved = 1").fetchone()[0]:
                conn.execute("ROLLBACK")
                return "Unresolved spend exists; reconcile it with `runport budget reconcile` before any further live request."
            booked = "SELECT COALESCE(SUM(amount_micros), 0) FROM budget_ledger WHERE is_simulated = 0 AND is_preflight_estimate = 0"
            held = "SELECT COALESCE(SUM(amount_micros), 0) FROM budget_reservations"
            total = conn.execute(booked).fetchone()[0] + conn.execute(held).fetchone()[0]
            run_total = conn.execute(booked + " AND run_id = ?", (run_id,)).fetchone()[0] + conn.execute(held + " WHERE run_id = ?", (run_id,)).fetchone()[0]
            pilot_total = conn.execute(booked + " AND is_pilot = 1").fetchone()[0] + conn.execute(held + " WHERE is_pilot = 1").fetchone()[0]

            def usd(m: int) -> str:
                return f"${Decimal(m) / Decimal('1000000'):.6f}"

            def micros(d: Decimal) -> int:
                return int((Decimal(d) * Decimal("1000000")).to_integral_value())

            reason = None
            if run_total + amount > micros(run_cap_usd):
                reason = f"per-run ceiling {usd(micros(run_cap_usd))} reached (this run has {usd(run_total)} spent or reserved)"
            elif total + amount > micros(total_cap_usd):
                reason = f"total ceiling {usd(micros(total_cap_usd))} reached ({usd(total)} spent or reserved)"
            elif is_pilot and pilot_total + amount > micros(pilot_cap_usd):
                reason = f"pilot ceiling {usd(micros(pilot_cap_usd))} reached ({usd(pilot_total)} spent or reserved)"
            if reason:
                conn.execute("ROLLBACK")
                return reason
            conn.execute(
                "INSERT INTO budget_reservations (reservation_id, run_id, amount_micros, is_pilot, created_at, expires_at) VALUES (?, ?, ?, ?, ?, ?)",
                (reservation_id, run_id, amount, 1 if is_pilot else 0, now, now + ttl_s),
            )
            conn.execute("COMMIT")
            return None
        except BaseException:
            if conn.in_transaction:
                conn.execute("ROLLBACK")
            raise
        finally:
            conn.close()

    def release_reservation(self, reservation_id: str) -> None:
        with self.get_connection() as conn:
            conn.execute("DELETE FROM budget_reservations WHERE reservation_id = ?", (reservation_id,))
            conn.commit()

    def get_open_reservations(self) -> tuple[int, Decimal]:
        import time as _time

        with self.get_connection() as conn:
            micros = conn.execute("SELECT COALESCE(SUM(amount_micros), 0) FROM budget_reservations WHERE expires_at > ?", (_time.time(),)).fetchone()[0]
        return micros, Decimal(micros) / Decimal("1000000")

    def get_pilot_spend(self, include_estimates: bool = False) -> tuple[int, Decimal]:
        """Returns spend attributed to pilot evaluation as (micros, Decimal)."""
        with self.get_connection() as conn:
            where_clause = "WHERE is_pilot = 1 AND is_simulated = 0"
            if not include_estimates:
                where_clause += " AND is_preflight_estimate = 0"
            cursor = conn.execute(f"SELECT COALESCE(SUM(amount_micros), 0) FROM budget_ledger {where_clause}")
            row = cursor.fetchone()
            micros = row[0] if row else 0
            return micros, Decimal(micros) / Decimal("1000000")

    def get_recent_transactions(self, limit: int = 15) -> List[Dict[str, Any]]:
        """Retrieves most recent ledger transactions."""
        with self.get_connection() as conn:
            cursor = conn.execute(
                """
                SELECT transaction_id, timestamp, run_id, model_id, provider,
                       amount_usd, amount_micros, is_pilot, is_preflight_estimate, is_simulated, is_unresolved, cost_basis, description
                FROM budget_ledger
                ORDER BY timestamp DESC
                LIMIT ?
                """,
                (limit,),
            )
            return [dict(row) for row in cursor.fetchall()]

    def upsert_model(
        self,
        model_id: str,
        display_name: str,
        provider: str,
        deployment_mode: str,
        license_type: str,
        context_length: Optional[int],
        input_price_per_1m_usd: str,
        output_price_per_1m_usd: str,
        verification_status: str,
        experimental_purpose: str,
    ) -> None:
        """Inserts or updates a model in the local portfolio registry."""
        now = datetime.now(timezone.utc).isoformat()
        with self.get_connection() as conn:
            conn.execute(
                """
                INSERT INTO model_portfolio (
                    model_id, display_name, provider, deployment_mode, license,
                    context_length, input_price_per_1m_usd, output_price_per_1m_usd,
                    verification_status, experimental_purpose, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(model_id) DO UPDATE SET
                    display_name = excluded.display_name,
                    provider = excluded.provider,
                    deployment_mode = excluded.deployment_mode,
                    license = excluded.license,
                    context_length = excluded.context_length,
                    input_price_per_1m_usd = excluded.input_price_per_1m_usd,
                    output_price_per_1m_usd = excluded.output_price_per_1m_usd,
                    verification_status = excluded.verification_status,
                    experimental_purpose = excluded.experimental_purpose
                """,
                (
                    model_id,
                    display_name,
                    provider,
                    deployment_mode,
                    license_type,
                    context_length,
                    input_price_per_1m_usd,
                    output_price_per_1m_usd,
                    verification_status,
                    experimental_purpose,
                    now,
                ),
            )
            conn.commit()

    def get_all_models(self) -> List[Dict[str, Any]]:
        """Returns all registered models from the portfolio."""
        with self.get_connection() as conn:
            cursor = conn.execute(
                """
                SELECT model_id, display_name, provider, deployment_mode, license,
                       context_length, input_price_per_1m_usd, output_price_per_1m_usd,
                       verification_status, experimental_purpose
                FROM model_portfolio
                ORDER BY deployment_mode, model_id
                """
            )
            return [dict(row) for row in cursor.fetchall()]

    def save_evaluation_run(self, run: Dict[str, Any]) -> None:
        """Saves a completed or aborted evaluation run header."""
        with self.get_connection() as conn:
            conn.execute(
                """
                INSERT INTO evaluation_runs (
                    run_id, timestamp, model_id, dataset_path, total_cases,
                    completed_cases, failed_cases, total_cost_usd, mean_latency_ms,
                    mean_accuracy, mean_groundedness, mean_overall_score, is_dry_run, notes
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(run_id) DO UPDATE SET
                    completed_cases = excluded.completed_cases,
                    failed_cases = excluded.failed_cases,
                    total_cost_usd = excluded.total_cost_usd,
                    mean_latency_ms = excluded.mean_latency_ms,
                    mean_accuracy = excluded.mean_accuracy,
                    mean_groundedness = excluded.mean_groundedness,
                    mean_overall_score = excluded.mean_overall_score,
                    notes = excluded.notes
                """,
                (
                    run["run_id"],
                    run["timestamp"],
                    run["model_id"],
                    run["dataset_path"],
                    run["total_cases"],
                    run["completed_cases"],
                    run["failed_cases"],
                    str(run["total_cost_usd"]) if run.get("total_cost_usd") is not None else "0.0000",
                    float(run["mean_latency_ms"]) if run.get("mean_latency_ms") is not None else None,
                    float(run["mean_accuracy"]) if run.get("mean_accuracy") is not None else None,
                    float(run["mean_groundedness"]) if run.get("mean_groundedness") is not None else None,
                    float(run["mean_overall_score"]) if run.get("mean_overall_score") is not None else None,
                    1 if run.get("is_dry_run", False) else 0,
                    run.get("notes", ""),
                ),
            )
            conn.commit()

    def save_evaluation_results(self, results: List[Dict[str, Any]]) -> None:
        """Batch inserts individual evaluation results."""
        with self.get_connection() as conn:
            conn.executemany(
                """
                INSERT INTO evaluation_results (
                    result_id, run_id, case_id, prompt, expected_answer,
                    generated_output, latency_ms, prompt_tokens, completion_tokens,
                    cost_usd, accuracy, groundedness, format_adherence, overall_score,
                    evaluator_notes, score_kind, evaluator
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(result_id) DO NOTHING
                """,
                [
                    (
                        r["result_id"],
                        r["run_id"],
                        r["case_id"],
                        r["prompt"],
                        r.get("expected_answer", ""),
                        r["generated_output"],
                        float(r["latency_ms"]) if r.get("latency_ms") is not None else None,
                        int(r["prompt_tokens"]) if r.get("prompt_tokens") is not None else None,
                        int(r["completion_tokens"]) if r.get("completion_tokens") is not None else None,
                        str(r["cost_usd"]) if r.get("cost_usd") is not None else None,
                        float(r["accuracy"]) if r.get("accuracy") is not None else None,
                        float(r["groundedness"]) if r.get("groundedness") is not None else None,
                        float(r["format_adherence"]) if r.get("format_adherence") is not None else None,
                        float(r["overall_score"]) if r.get("overall_score") is not None else None,
                        r.get("evaluator_notes", ""),
                        r.get("score_kind"),
                        r.get("evaluator"),
                    )
                    for r in results
                ],
            )
            conn.commit()

    def get_evaluation_run(self, run_id: str) -> Optional[Dict[str, Any]]:
        """Fetches a specific evaluation run by ID."""
        with self.get_connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM evaluation_runs WHERE run_id = ?",
                (run_id,),
            )
            row = cursor.fetchone()
            return dict(row) if row else None

    def get_all_evaluation_runs(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Returns recent evaluation runs sorted newest first."""
        with self.get_connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM evaluation_runs ORDER BY timestamp DESC LIMIT ?",
                (limit,),
            )
            return [dict(row) for row in cursor.fetchall()]

    def get_evaluation_results_for_run(self, run_id: str) -> List[Dict[str, Any]]:
        """Returns all individual results for a run."""
        with self.get_connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM evaluation_results WHERE run_id = ? ORDER BY result_id",
                (run_id,),
            )
            return [dict(row) for row in cursor.fetchall()]

    # -------------------------------------------------------------------------
    # Canonical Trace & Span Persistence (Milestone 2 - Phase 1)
    # -------------------------------------------------------------------------

    def create_trace(self, trace: Trace) -> None:
        """Persists a new trace record. Fails with IntegrityError if trace_id already exists."""
        with self.get_connection() as conn:
            conn.execute(
                """
                INSERT INTO traces (
                    trace_id, run_id, case_id, target_id, session_id, name, status,
                    start_time, end_time, attributes_json, schema_version, source, source_ref, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    trace.trace_id,
                    trace.run_id,
                    trace.case_id,
                    trace.target_id,
                    trace.session_id,
                    trace.name,
                    trace.status.value,
                    trace.start_time.isoformat() if trace.start_time else None,
                    trace.end_time.isoformat() if trace.end_time else None,
                    json.dumps(trace.attributes),
                    trace.schema_version,
                    trace.source,
                    trace.source_ref,
                    trace.created_at.isoformat(),
                ),
            )
            if trace.spans:
                self._insert_spans_with_conn(conn, trace.spans)
            conn.commit()

    def save_trace(self, trace: Trace) -> None:
        """Upserts a trace and any child spans atomically in a single transaction."""
        with self.get_connection() as conn:
            conn.execute(
                """
                INSERT INTO traces (
                    trace_id, run_id, case_id, target_id, session_id, name, status,
                    start_time, end_time, attributes_json, schema_version, source, source_ref, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(trace_id) DO UPDATE SET
                    run_id=excluded.run_id,
                    case_id=excluded.case_id,
                    target_id=excluded.target_id,
                    session_id=excluded.session_id,
                    name=excluded.name,
                    status=excluded.status,
                    start_time=excluded.start_time,
                    end_time=excluded.end_time,
                    attributes_json=excluded.attributes_json,
                    schema_version=excluded.schema_version,
                    source=excluded.source,
                    source_ref=excluded.source_ref
                """,
                (
                    trace.trace_id,
                    trace.run_id,
                    trace.case_id,
                    trace.target_id,
                    trace.session_id,
                    trace.name,
                    trace.status.value,
                    trace.start_time.isoformat() if trace.start_time else None,
                    trace.end_time.isoformat() if trace.end_time else None,
                    json.dumps(trace.attributes),
                    trace.schema_version,
                    trace.source,
                    trace.source_ref,
                    trace.created_at.isoformat(),
                ),
            )
            if trace.spans:
                for span in trace.spans:
                    self._upsert_span_with_conn(conn, span)
            conn.commit()

    def create_span(self, span: Span) -> None:
        """Persists a new span record. Fails with IntegrityError if span already exists."""
        with self.get_connection() as conn:
            self._insert_span_with_conn(conn, span)
            conn.commit()

    def create_spans(self, spans: List[Span]) -> None:
        """Persists multiple spans in an atomic transaction. Rolls back entirely on failure."""
        if not spans:
            return
        with self.get_connection() as conn:
            self._insert_spans_with_conn(conn, spans)
            conn.commit()

    def _insert_span_with_conn(self, conn: sqlite3.Connection, span: Span) -> None:
        events_json = json.dumps([e.model_dump(mode="json") for e in span.events])
        conn.execute(
            """
            INSERT INTO spans (
                trace_id, span_id, parent_span_id, name, kind, status,
                start_time, end_time, duration_ms, provider, model,
                prompt_tokens, completion_tokens, total_tokens,
                cost_usd, cost_basis, attributes_json, events_json,
                error_json, attempt, source, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                span.trace_id,
                span.span_id,
                span.parent_span_id,
                span.name,
                span.kind.value,
                span.status.value,
                span.start_time.isoformat() if span.start_time else None,
                span.end_time.isoformat() if span.end_time else None,
                span.duration_ms,
                span.provider,
                span.model,
                span.prompt_tokens,
                span.completion_tokens,
                span.total_tokens,
                span.cost_usd,
                span.cost_basis,
                json.dumps(span.attributes),
                events_json,
                span.error,
                span.attempt,
                span.source,
                span.created_at.isoformat(),
            ),
        )

    def _upsert_span_with_conn(self, conn: sqlite3.Connection, span: Span) -> None:
        events_json = json.dumps([e.model_dump(mode="json") for e in span.events])
        conn.execute(
            """
            INSERT INTO spans (
                trace_id, span_id, parent_span_id, name, kind, status,
                start_time, end_time, duration_ms, provider, model,
                prompt_tokens, completion_tokens, total_tokens,
                cost_usd, cost_basis, attributes_json, events_json,
                error_json, attempt, source, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(trace_id, span_id) DO UPDATE SET
                parent_span_id=excluded.parent_span_id,
                name=excluded.name,
                kind=excluded.kind,
                status=excluded.status,
                start_time=excluded.start_time,
                end_time=excluded.end_time,
                duration_ms=excluded.duration_ms,
                provider=excluded.provider,
                model=excluded.model,
                prompt_tokens=excluded.prompt_tokens,
                completion_tokens=excluded.completion_tokens,
                total_tokens=excluded.total_tokens,
                cost_usd=excluded.cost_usd,
                cost_basis=excluded.cost_basis,
                attributes_json=excluded.attributes_json,
                events_json=excluded.events_json,
                error_json=excluded.error_json,
                attempt=excluded.attempt,
                source=excluded.source
            """,
            (
                span.trace_id,
                span.span_id,
                span.parent_span_id,
                span.name,
                span.kind.value,
                span.status.value,
                span.start_time.isoformat() if span.start_time else None,
                span.end_time.isoformat() if span.end_time else None,
                span.duration_ms,
                span.provider,
                span.model,
                span.prompt_tokens,
                span.completion_tokens,
                span.total_tokens,
                span.cost_usd,
                span.cost_basis,
                json.dumps(span.attributes),
                events_json,
                span.error,
                span.attempt,
                span.source,
                span.created_at.isoformat(),
            ),
        )

    def _insert_spans_with_conn(self, conn: sqlite3.Connection, spans: List[Span]) -> None:
        for span in spans:
            self._insert_span_with_conn(conn, span)

    def get_trace(self, trace_id: str, include_spans: bool = True) -> Optional[Trace]:
        """Fetches a trace by ID. Optionally populates child spans."""
        with self.get_connection() as conn:
            cursor = conn.execute("SELECT * FROM traces WHERE trace_id = ?", (trace_id,))
            row = cursor.fetchone()
            if not row:
                return None
            spans: List[Span] = []
            if include_spans:
                s_cursor = conn.execute(
                    "SELECT * FROM spans WHERE trace_id = ? ORDER BY start_time ASC, created_at ASC",
                    (trace_id,),
                )
                spans = [self._row_to_span(r) for r in s_cursor.fetchall()]
            return self._row_to_trace(row, spans=spans)

    def get_spans(self, trace_id: str) -> List[Span]:
        """Fetches all spans for a given trace ordered chronologically."""
        with self.get_connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM spans WHERE trace_id = ? ORDER BY start_time ASC, created_at ASC",
                (trace_id,),
            )
            return [self._row_to_span(r) for r in cursor.fetchall()]

    def get_spans_by_parent(self, trace_id: str, parent_span_id: Optional[str]) -> List[Span]:
        """Fetches spans within a trace filtered by immediate parent span."""
        with self.get_connection() as conn:
            if parent_span_id is None:
                cursor = conn.execute(
                    "SELECT * FROM spans WHERE trace_id = ? AND parent_span_id IS NULL ORDER BY start_time ASC, created_at ASC",
                    (trace_id,),
                )
            else:
                cursor = conn.execute(
                    "SELECT * FROM spans WHERE trace_id = ? AND parent_span_id = ? ORDER BY start_time ASC, created_at ASC",
                    (trace_id, parent_span_id),
                )
            return [self._row_to_span(r) for r in cursor.fetchall()]

    def get_traces_for_run(self, run_id: str, include_spans: bool = False) -> List[Trace]:
        """Returns all traces associated with a specific evaluation run."""
        with self.get_connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM traces WHERE run_id = ? ORDER BY start_time ASC, created_at ASC",
                (run_id,),
            )
            rows = cursor.fetchall()
            traces = []
            for r in rows:
                spans = self.get_spans(r["trace_id"]) if include_spans else []
                traces.append(self._row_to_trace(r, spans=spans))
            return traces

    def get_traces_for_case(self, run_id: str, case_id: str, include_spans: bool = False) -> List[Trace]:
        """Returns all traces for a specific run case."""
        with self.get_connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM traces WHERE run_id = ? AND case_id = ? ORDER BY start_time ASC, created_at ASC",
                (run_id, case_id),
            )
            rows = cursor.fetchall()
            traces = []
            for r in rows:
                spans = self.get_spans(r["trace_id"]) if include_spans else []
                traces.append(self._row_to_trace(r, spans=spans))
            return traces

    def list_traces(self, limit: int = 50, include_spans: bool = False) -> List[Trace]:
        """Returns the most recent canonical traces across all runs."""
        with self.get_connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM traces ORDER BY start_time DESC, created_at DESC LIMIT ?",
                (max(1, limit),),
            )
            rows = cursor.fetchall()
            traces = []
            for r in rows:
                spans = self.get_spans(r["trace_id"]) if include_spans else []
                traces.append(self._row_to_trace(r, spans=spans))
            return traces

    def update_trace_status(
        self,
        trace_id: str,
        status: SpanStatus,
        end_time: Optional[datetime] = None,
    ) -> None:
        """Updates the status and optional end_time of an existing trace."""
        with self.get_connection() as conn:
            cur = conn.execute("SELECT 1 FROM traces WHERE trace_id = ?", (trace_id,))
            if not cur.fetchone():
                raise KeyError(f"Trace not found: {trace_id}")

            status_val = status.value if hasattr(status, "value") else str(status)
            if end_time is not None:
                dt = _to_utc_dt(end_time)
                end_iso = dt.isoformat() if dt else None
                conn.execute(
                    "UPDATE traces SET status = ?, end_time = ? WHERE trace_id = ?",
                    (status_val, end_iso, trace_id),
                )
            else:
                conn.execute(
                    "UPDATE traces SET status = ? WHERE trace_id = ?",
                    (status_val, trace_id),
                )
            conn.commit()

    def update_span_status(
        self,
        trace_id: str,
        span_id: str,
        status: SpanStatus,
        end_time: Optional[datetime] = None,
        error: Optional[str] = None,
    ) -> None:
        """Updates status, end_time, and sanitized error for an existing span."""
        with self.get_connection() as conn:
            cur = conn.execute(
                "SELECT start_time FROM spans WHERE trace_id = ? AND span_id = ?",
                (trace_id, span_id),
            )
            row = cur.fetchone()
            if not row:
                raise KeyError(f"Span not found: trace_id={trace_id}, span_id={span_id}")

            from runport.providers.base import scrub_secrets

            status_val = status.value if hasattr(status, "value") else str(status)
            scrubbed_error = scrub_secrets(str(error)) if error is not None else None

            if end_time is not None:
                dt = _to_utc_dt(end_time)
                end_iso = dt.isoformat() if dt else None
                start_iso = row["start_time"]
                duration_ms = None
                if start_iso and dt:
                    start_dt = datetime.fromisoformat(start_iso)
                    if dt < start_dt:
                        raise ValueError(f"end_time ({dt}) cannot be earlier than start_time ({start_dt})")
                    duration_ms = max(0.0, round((dt - start_dt).total_seconds() * 1000.0, 3))

                conn.execute(
                    """
                    UPDATE spans 
                    SET status = ?, end_time = ?, duration_ms = COALESCE(?, duration_ms), error_json = COALESCE(?, error_json)
                    WHERE trace_id = ? AND span_id = ?
                    """,
                    (status_val, end_iso, duration_ms, scrubbed_error, trace_id, span_id),
                )
            else:
                conn.execute(
                    """
                    UPDATE spans 
                    SET status = ?, error_json = COALESCE(?, error_json)
                    WHERE trace_id = ? AND span_id = ?
                    """,
                    (status_val, scrubbed_error, trace_id, span_id),
                )
            conn.commit()

    @staticmethod
    def _row_to_trace(row: sqlite3.Row, spans: Optional[List[Span]] = None) -> Trace:
        from runport.traces.domain import SpanStatus, Trace

        return Trace(
            trace_id=row["trace_id"],
            run_id=row["run_id"],
            case_id=row["case_id"],
            target_id=row["target_id"],
            session_id=row["session_id"],
            name=row["name"],
            status=SpanStatus(row["status"]),
            start_time=datetime.fromisoformat(row["start_time"]) if row["start_time"] else None,
            end_time=datetime.fromisoformat(row["end_time"]) if row["end_time"] else None,
            attributes=json.loads(row["attributes_json"]) if row["attributes_json"] else {},
            schema_version=row["schema_version"],
            source=row["source"],
            source_ref=row["source_ref"],
            created_at=datetime.fromisoformat(row["created_at"]) if row["created_at"] else datetime.now(timezone.utc),
            spans=spans or [],
        )

    @staticmethod
    def _row_to_span(row: sqlite3.Row) -> Span:
        from runport.traces.domain import Span, SpanEvent, SpanKind, SpanStatus

        events_data = json.loads(row["events_json"]) if row["events_json"] else []
        events = [
            SpanEvent(
                name=e["name"],
                timestamp=e["timestamp"],
                attributes=e.get("attributes", {}),
            )
            for e in events_data
        ]
        return Span(
            trace_id=row["trace_id"],
            span_id=row["span_id"],
            parent_span_id=row["parent_span_id"],
            name=row["name"],
            kind=SpanKind(row["kind"]),
            status=SpanStatus(row["status"]),
            start_time=datetime.fromisoformat(row["start_time"]) if row["start_time"] else None,
            end_time=datetime.fromisoformat(row["end_time"]) if row["end_time"] else None,
            duration_ms=row["duration_ms"],
            provider=row["provider"],
            model=row["model"],
            prompt_tokens=row["prompt_tokens"],
            completion_tokens=row["completion_tokens"],
            total_tokens=row["total_tokens"],
            cost_usd=row["cost_usd"],
            cost_basis=row["cost_basis"],
            attributes=json.loads(row["attributes_json"]) if row["attributes_json"] else {},
            events=events,
            error=row["error_json"],
            attempt=row["attempt"],
            source=row["source"],
            created_at=datetime.fromisoformat(row["created_at"]) if row["created_at"] else datetime.now(timezone.utc),
        )

"""SQLite database initialization, migration, and transactional persistence."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timedelta, timezone
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
    expires_at REAL NOT NULL,
    project_id TEXT NOT NULL DEFAULT 'default',
    plan_id TEXT
);

CREATE TABLE IF NOT EXISTS idempotency_records (
    key TEXT NOT NULL,
    project_id TEXT NOT NULL DEFAULT 'default',
    action TEXT NOT NULL,
    resource_id TEXT,
    response_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    PRIMARY KEY (project_id, key)
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

CREATE TABLE IF NOT EXISTS api_keys (
    key_id TEXT PRIMARY KEY,
    key_hash TEXT NOT NULL,
    name TEXT NOT NULL,
    scopes_json TEXT NOT NULL DEFAULT '[]',
    created_at TEXT NOT NULL,
    expires_at TEXT,
    revoked INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_api_keys_hash ON api_keys(key_hash);

CREATE TABLE IF NOT EXISTS run_jobs (
    job_id TEXT PRIMARY KEY,
    plan_id TEXT NOT NULL,
    run_id TEXT,
    status TEXT NOT NULL,
    total_cases INTEGER NOT NULL DEFAULT 0,
    completed_cases INTEGER NOT NULL DEFAULT 0,
    failed_cases INTEGER NOT NULL DEFAULT 0,
    booked_spend_usd TEXT,
    error_message TEXT,
    cancelled INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    finished_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_run_jobs_plan_id ON run_jobs(plan_id);
CREATE INDEX IF NOT EXISTS idx_run_jobs_status ON run_jobs(status);

CREATE TABLE IF NOT EXISTS organizations (
    org_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS projects (
    project_id TEXT PRIMARY KEY,
    org_id TEXT NOT NULL,
    name TEXT NOT NULL,
    settings_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    FOREIGN KEY (org_id) REFERENCES organizations(org_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS memberships (
    membership_id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    project_id TEXT NOT NULL,
    role TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY (project_id) REFERENCES projects(project_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS audit_log (
    audit_id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    principal TEXT NOT NULL,
    action TEXT NOT NULL,
    resource_type TEXT,
    resource_id TEXT,
    details_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_projects_org ON projects(org_id);
CREATE INDEX IF NOT EXISTS idx_memberships_user ON memberships(user_id);
CREATE INDEX IF NOT EXISTS idx_memberships_project ON memberships(project_id);
CREATE INDEX IF NOT EXISTS idx_memberships_user_project ON memberships(user_id, project_id);
CREATE INDEX IF NOT EXISTS idx_audit_log_project ON audit_log(project_id);

"""


class DatabaseManager:
    """Manages SQLite connections, idempotent schemas, and budget ledger records."""

    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = Path(db_path) if db_path is not None else settings.db_path

    def get_connection(self) -> sqlite3.Connection:
        """Opens a connection with WAL mode and row factory."""
        if str(self.db_path) != ":memory:":
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(self.db_path), timeout=30.0)
        conn.row_factory = sqlite3.Row
        if str(self.db_path) != ":memory:":
            conn.execute("PRAGMA journal_mode = WAL;")
            conn.execute("PRAGMA busy_timeout = 30000;")
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
            self._migrate_api_v1_and_jobs(conn)
            self._migrate_multi_tenancy_and_rbac(conn)
            self._migrate_tenant_resource_ownership(conn)
            self._migrate_idempotency_and_reservations(conn)

    @staticmethod
    def _add_column_if_missing(conn: sqlite3.Connection, table: str, column_def: str) -> None:
        """Idempotently adds a column to an existing table, safely ignoring duplicate column errors."""
        col_name = column_def.split()[0].strip()
        cols = {r[1] for r in conn.execute(f"PRAGMA table_info({table})").fetchall()}
        if col_name not in cols:
            try:
                conn.execute(f"ALTER TABLE {table} ADD COLUMN {column_def}")
            except sqlite3.OperationalError as e:
                if "duplicate column name" not in str(e).lower():
                    raise

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
        DatabaseManager._add_column_if_missing(conn, "evaluation_results", "score_kind TEXT")
        DatabaseManager._add_column_if_missing(conn, "evaluation_results", "evaluator TEXT")

    @staticmethod
    def _migrate_ledger(conn: sqlite3.Connection) -> None:
        """Separate simulated from actual spend in ledgers created before the column existed.

        Legacy rows are marked simulated ONLY when the run they belong to is recorded as a dry run (evaluation_runs.is_dry_run = 1).
        Rows with no such evidence stay counted as actual, which is the conservative choice for a spend ceiling.
        """
        DatabaseManager._add_column_if_missing(conn, "budget_ledger", "is_simulated INTEGER NOT NULL DEFAULT 0")
        DatabaseManager._add_column_if_missing(conn, "budget_ledger", "is_unresolved INTEGER NOT NULL DEFAULT 0")
        DatabaseManager._add_column_if_missing(conn, "budget_ledger", "cost_basis TEXT NOT NULL DEFAULT 'UNSPECIFIED'")
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

    @staticmethod
    def _migrate_api_v1_and_jobs(conn: sqlite3.Connection) -> None:
        """Additive migration 5: Ensure api_keys and run_jobs tables and indexes exist.

        Preserves all existing tables and data. Safe for existing user databases.
        """
        tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
        if "api_keys" not in tables:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS api_keys (
                    key_id TEXT PRIMARY KEY,
                    key_hash TEXT NOT NULL,
                    name TEXT NOT NULL,
                    scopes_json TEXT NOT NULL DEFAULT '[]',
                    created_at TEXT NOT NULL,
                    expires_at TEXT,
                    revoked INTEGER NOT NULL DEFAULT 0
                )
            """)
        if "run_jobs" not in tables:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS run_jobs (
                    job_id TEXT PRIMARY KEY,
                    plan_id TEXT NOT NULL,
                    run_id TEXT,
                    status TEXT NOT NULL,
                    total_cases INTEGER NOT NULL DEFAULT 0,
                    completed_cases INTEGER NOT NULL DEFAULT 0,
                    failed_cases INTEGER NOT NULL DEFAULT 0,
                    booked_spend_usd TEXT,
                    error_message TEXT,
                    cancelled INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    finished_at TEXT
                )
            """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_api_keys_hash ON api_keys(key_hash)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_run_jobs_plan_id ON run_jobs(plan_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_run_jobs_status ON run_jobs(status)")
        conn.execute(
            "INSERT OR IGNORE INTO schema_migrations (version, applied_at, description) "
            "VALUES (5, datetime('now'), 'Add api_keys and run_jobs tables and indexes')"
        )
        conn.commit()

    @staticmethod
    def _migrate_multi_tenancy_and_rbac(conn: sqlite3.Connection) -> None:
        """Additive migration 6: Multi-tenant organizations, projects, memberships, audit_log, and project scoping.

        Preserves all existing tables and data. Ensures default organization and project exist for local single-user mode.
        """
        tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
        if "organizations" not in tables:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS organizations (
                    org_id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
            """)
        if "projects" not in tables:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS projects (
                    project_id TEXT PRIMARY KEY,
                    org_id TEXT NOT NULL,
                    name TEXT NOT NULL,
                    settings_json TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (org_id) REFERENCES organizations(org_id) ON DELETE CASCADE
                )
            """)
        if "memberships" not in tables:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS memberships (
                    membership_id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    project_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (project_id) REFERENCES projects(project_id) ON DELETE CASCADE
                )
            """)
        if "audit_log" not in tables:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS audit_log (
                    audit_id TEXT PRIMARY KEY,
                    project_id TEXT NOT NULL,
                    principal TEXT NOT NULL,
                    action TEXT NOT NULL,
                    resource_type TEXT,
                    resource_id TEXT,
                    details_json TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT NOT NULL
                )
            """)

        # Add project_id, principal, last_used_at to api_keys if missing
        if "api_keys" in tables:
            DatabaseManager._add_column_if_missing(conn, "api_keys", "project_id TEXT NOT NULL DEFAULT 'default'")
            DatabaseManager._add_column_if_missing(conn, "api_keys", "principal TEXT")
            DatabaseManager._add_column_if_missing(conn, "api_keys", "last_used_at TEXT")

        # Add project_id to evaluation_runs if missing
        if "evaluation_runs" in tables:
            DatabaseManager._add_column_if_missing(conn, "evaluation_runs", "project_id TEXT NOT NULL DEFAULT 'default'")

        # Add project_id to traces if missing
        if "traces" in tables:
            DatabaseManager._add_column_if_missing(conn, "traces", "project_id TEXT NOT NULL DEFAULT 'default'")

        # Add project_id to budget_ledger if missing
        if "budget_ledger" in tables:
            DatabaseManager._add_column_if_missing(conn, "budget_ledger", "project_id TEXT NOT NULL DEFAULT 'default'")

        # Seed default organization and project for local single-tenant mode
        conn.execute("""
            INSERT OR IGNORE INTO organizations (org_id, name, created_at)
            VALUES ('default-org', 'Default Organization', datetime('now'))
        """)
        conn.execute("""
            INSERT OR IGNORE INTO projects (project_id, org_id, name, settings_json, created_at)
            VALUES ('default', 'default-org', 'Default Project', '{}', datetime('now'))
        """)

        # Create indexes
        conn.execute("CREATE INDEX IF NOT EXISTS idx_projects_org ON projects(org_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_memberships_user ON memberships(user_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_memberships_project ON memberships(project_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_memberships_user_project ON memberships(user_id, project_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_audit_log_project ON audit_log(project_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_api_keys_project ON api_keys(project_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_traces_project ON traces(project_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_runs_project ON evaluation_runs(project_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_ledger_project ON budget_ledger(project_id)")

        conn.execute(
            "INSERT OR IGNORE INTO schema_migrations (version, applied_at, description) "
            "VALUES (6, datetime('now'), 'Add multi-tenant organizations, projects, memberships, audit_log tables and project scoping')"
        )
        conn.commit()

    @staticmethod
    def _migrate_tenant_resource_ownership(conn: sqlite3.Connection) -> None:
        """Additive migration 7: Project-level resource ownership and worker lease metadata.

        Adds project_id and worker lease columns to run_jobs and plan_approvals.
        Establishes indexes idx_run_jobs_project_status and idx_plan_approvals_project.
        """
        tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}

        if "run_jobs" in tables:
            DatabaseManager._add_column_if_missing(conn, "run_jobs", "project_id TEXT NOT NULL DEFAULT 'default'")
            DatabaseManager._add_column_if_missing(conn, "run_jobs", "requested_by_key_id TEXT")
            DatabaseManager._add_column_if_missing(conn, "run_jobs", "worker_id TEXT")
            DatabaseManager._add_column_if_missing(conn, "run_jobs", "lease_expires_at TEXT")
            DatabaseManager._add_column_if_missing(conn, "run_jobs", "heartbeat_at TEXT")
            DatabaseManager._add_column_if_missing(conn, "run_jobs", "attempt_count INTEGER NOT NULL DEFAULT 0")
            DatabaseManager._add_column_if_missing(conn, "run_jobs", "started_at TEXT")
            DatabaseManager._add_column_if_missing(conn, "run_jobs", "cancelled_at TEXT")

            conn.execute("CREATE INDEX IF NOT EXISTS idx_run_jobs_project ON run_jobs(project_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_run_jobs_project_status ON run_jobs(project_id, status)")

        if "plan_approvals" in tables:
            DatabaseManager._add_column_if_missing(conn, "plan_approvals", "project_id TEXT NOT NULL DEFAULT 'default'")

            conn.execute("CREATE INDEX IF NOT EXISTS idx_plan_approvals_project ON plan_approvals(project_id)")

        conn.execute(
            "INSERT OR IGNORE INTO schema_migrations (version, applied_at, description) "
            "VALUES (7, datetime('now'), 'Add project_id and worker lease columns to run_jobs and plan_approvals')"
        )
        conn.commit()

    @staticmethod
    def _migrate_idempotency_and_reservations(conn: sqlite3.Connection) -> None:
        """Additive migration 8: Idempotency keys, records, and budget reservation project scoping.

        Adds idempotency_key to run_jobs with unique partial index on (project_id, idempotency_key).
        Adds project_id to budget_reservations.
        Creates idempotency_records table for reusable idempotent action records.
        """
        tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}

        if "run_jobs" in tables:
            DatabaseManager._add_column_if_missing(conn, "run_jobs", "idempotency_key TEXT")
            DatabaseManager._add_column_if_missing(conn, "run_jobs", "requested_by TEXT")
            conn.execute(
                "CREATE UNIQUE INDEX IF NOT EXISTS idx_run_jobs_project_idempotency ON run_jobs(project_id, idempotency_key) WHERE idempotency_key IS NOT NULL"
            )

        if "budget_reservations" in tables:
            DatabaseManager._add_column_if_missing(conn, "budget_reservations", "project_id TEXT NOT NULL DEFAULT 'default'")
            DatabaseManager._add_column_if_missing(conn, "budget_reservations", "plan_id TEXT")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_budget_reservations_project ON budget_reservations(project_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_budget_reservations_run ON budget_reservations(run_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_budget_reservations_plan ON budget_reservations(plan_id)")

        if "idempotency_records" not in tables:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS idempotency_records (
                    key TEXT NOT NULL,
                    project_id TEXT NOT NULL DEFAULT 'default',
                    action TEXT NOT NULL,
                    resource_id TEXT,
                    response_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    PRIMARY KEY (project_id, key)
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_idempotency_records_action ON idempotency_records(project_id, action)")

        conn.execute(
            "INSERT OR IGNORE INTO schema_migrations (version, applied_at, description) "
            "VALUES (8, datetime('now'), 'Add idempotency_key to run_jobs, project_id to budget_reservations, and idempotency_records table')"
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
        project_id: str = "default",
    ) -> bool:
        """Records a new entry in the budget ledger using exact integer micros and Decimal string.

        Idempotent: if transaction_id already exists, returns False and does not duplicate spend.
        Returns True if newly committed.
        """
        if timestamp is None:
            timestamp = datetime.now(timezone.utc).isoformat()

        amount_micros = int(amount_usd * 1_000_000)
        formatted_usd = f"{amount_usd:.6f}"

        with self.get_connection() as conn:
            cur = conn.execute(
                """
                INSERT OR IGNORE INTO budget_ledger (
                    transaction_id, timestamp, run_id, model_id, provider,
                    amount_micros, amount_usd, is_pilot, is_preflight_estimate, is_simulated, is_unresolved, cost_basis, description, project_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                    project_id,
                ),
            )
            conn.commit()
            return cur.rowcount == 1

    def get_cumulative_spend(self, include_estimates: bool = False, project_id: Optional[str] = None) -> tuple[int, Decimal]:
        """Returns total historical spend as (micros, Decimal), optionally scoped by project."""
        with self.get_connection() as conn:
            where_clause = "WHERE is_simulated = 0" + ("" if include_estimates else " AND is_preflight_estimate = 0")
            params: List[Any] = []
            if project_id is not None:
                where_clause += " AND project_id = ?"
                params.append(project_id)
            cursor = conn.execute(f"SELECT COALESCE(SUM(amount_micros), 0) FROM budget_ledger {where_clause}", params)
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

    def get_unresolved(self, project_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Ledger entries for requests that may have been billed but whose cost is unknown, optionally scoped by project."""
        with self.get_connection() as conn:
            where_clause = "WHERE is_unresolved = 1"
            params: List[Any] = []
            if project_id is not None:
                where_clause += " AND project_id = ?"
                params.append(project_id)
            cur = conn.execute(
                f"SELECT transaction_id, timestamp, run_id, model_id, provider, description, project_id FROM budget_ledger {where_clause} ORDER BY timestamp",
                params,
            )
            return [dict(r) for r in cur.fetchall()]

    def reconcile_transaction(self, transaction_id: str, amount_usd: Decimal, note: str = "", project_id: Optional[str] = None) -> None:
        """Resolve an unresolved entry with an amount the operator read from the provider dashboard (recorded as RECONCILED_MANUAL)."""
        with self.get_connection() as conn:
            where_clause = "WHERE transaction_id = ?"
            params: List[Any] = [transaction_id]
            if project_id is not None:
                where_clause += " AND project_id = ?"
                params.append(project_id)
            row = conn.execute(f"SELECT is_unresolved FROM budget_ledger {where_clause}", params).fetchone()
            if row is None:
                raise KeyError(f"No ledger entry {transaction_id}")
            if not row[0]:
                raise ValueError(f"Ledger entry {transaction_id} is not unresolved")
            conn.execute(
                f"UPDATE budget_ledger SET is_unresolved = 0, amount_micros = ?, amount_usd = ?, cost_basis = 'RECONCILED_MANUAL', "
                f"description = description || ? {where_clause}",
                [int(amount_usd * 1_000_000), f"{amount_usd:.6f}", f" [reconciled manually: {note or 'amount from provider dashboard'}]"] + params,
            )
            conn.commit()

    def get_spend_by_basis(self, project_id: Optional[str] = None) -> Dict[str, Decimal]:
        """Actual-side spend grouped by how the cost was established (simulated and pre-run estimates excluded)."""
        with self.get_connection() as conn:
            where_clause = "WHERE is_simulated = 0 AND is_preflight_estimate = 0 AND is_unresolved = 0"
            params: List[Any] = []
            if project_id is not None:
                where_clause += " AND project_id = ?"
                params.append(project_id)
            cur = conn.execute(
                f"SELECT cost_basis, COALESCE(SUM(amount_micros), 0) FROM budget_ledger {where_clause} GROUP BY cost_basis",
                params,
            )
            return {b: Decimal(m) / Decimal("1000000") for b, m in cur.fetchall()}

    def get_simulated_spend(self, project_id: Optional[str] = None) -> tuple[int, Decimal]:
        """Returns spend recorded by dry-run simulations. It never counts against any ceiling."""
        with self.get_connection() as conn:
            where_clause = "WHERE is_simulated = 1"
            params: List[Any] = []
            if project_id is not None:
                where_clause += " AND project_id = ?"
                params.append(project_id)
            row = conn.execute(f"SELECT COALESCE(SUM(amount_micros), 0) FROM budget_ledger {where_clause}", params).fetchone()
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
        project_id: str = "default",
        plan_id: Optional[str] = None,
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
            if str(self.db_path) != ":memory:":
                conn.execute("PRAGMA journal_mode = WAL;")
                conn.execute("PRAGMA busy_timeout = 30000;")
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

            cols = {r[1] for r in conn.execute("PRAGMA table_info(budget_reservations)").fetchall()}
            if "project_id" in cols and "plan_id" in cols:
                conn.execute(
                    "INSERT INTO budget_reservations (reservation_id, run_id, amount_micros, is_pilot, created_at, expires_at, project_id, plan_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (reservation_id, run_id, amount, 1 if is_pilot else 0, now, now + ttl_s, project_id, plan_id),
                )
            elif "project_id" in cols:
                conn.execute(
                    "INSERT INTO budget_reservations (reservation_id, run_id, amount_micros, is_pilot, created_at, expires_at, project_id) VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (reservation_id, run_id, amount, 1 if is_pilot else 0, now, now + ttl_s, project_id),
                )
            else:
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

    def release_run_reservations(self, run_id: str) -> int:
        """Releases all open budget reservations for a specific run ID."""
        with self.get_connection() as conn:
            cur = conn.execute("DELETE FROM budget_reservations WHERE run_id = ?", (run_id,))
            conn.commit()
            return cur.rowcount

    def release_plan_reservations(self, plan_id: str) -> int:
        """Releases all open budget reservations for a specific plan ID."""
        with self.get_connection() as conn:
            cur = conn.execute("DELETE FROM budget_reservations WHERE plan_id = ?", (plan_id,))
            conn.commit()
            return cur.rowcount

    def get_open_reservations(self) -> tuple[int, Decimal]:
        import time as _time

        with self.get_connection() as conn:
            micros = conn.execute("SELECT COALESCE(SUM(amount_micros), 0) FROM budget_reservations WHERE expires_at > ?", (_time.time(),)).fetchone()[0]
        return micros, Decimal(micros) / Decimal("1000000")

    def get_pilot_spend(self, include_estimates: bool = False, project_id: Optional[str] = None) -> tuple[int, Decimal]:
        """Returns spend attributed to pilot evaluation as (micros, Decimal), optionally scoped by project."""
        with self.get_connection() as conn:
            where_clause = "WHERE is_pilot = 1 AND is_simulated = 0"
            if not include_estimates:
                where_clause += " AND is_preflight_estimate = 0"
            params: List[Any] = []
            if project_id is not None:
                where_clause += " AND project_id = ?"
                params.append(project_id)
            cursor = conn.execute(f"SELECT COALESCE(SUM(amount_micros), 0) FROM budget_ledger {where_clause}", params)
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
        pid = run.get("project_id", "default")
        with self.get_connection() as conn:
            conn.execute(
                """
                INSERT INTO evaluation_runs (
                    run_id, timestamp, model_id, dataset_path, total_cases,
                    completed_cases, failed_cases, total_cost_usd, mean_latency_ms,
                    mean_accuracy, mean_groundedness, mean_overall_score, is_dry_run, notes, project_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(run_id) DO UPDATE SET
                    completed_cases = excluded.completed_cases,
                    failed_cases = excluded.failed_cases,
                    total_cost_usd = excluded.total_cost_usd,
                    mean_latency_ms = excluded.mean_latency_ms,
                    mean_accuracy = excluded.mean_accuracy,
                    mean_groundedness = excluded.mean_groundedness,
                    mean_overall_score = excluded.mean_overall_score,
                    notes = excluded.notes,
                    project_id = excluded.project_id
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
                    pid,
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

    def get_evaluation_run(self, run_id: str, project_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Fetches a specific evaluation run by ID, optionally filtered by project_id."""
        with self.get_connection() as conn:
            if project_id:
                cursor = conn.execute(
                    "SELECT * FROM evaluation_runs WHERE run_id = ? AND project_id = ?",
                    (run_id, project_id),
                )
            else:
                cursor = conn.execute(
                    "SELECT * FROM evaluation_runs WHERE run_id = ?",
                    (run_id,),
                )
            row = cursor.fetchone()
            return dict(row) if row else None

    def get_all_evaluation_runs(self, limit: int = 50, project_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Returns recent evaluation runs sorted newest first, optionally filtered by project_id."""
        with self.get_connection() as conn:
            if project_id:
                cursor = conn.execute(
                    "SELECT * FROM evaluation_runs WHERE project_id = ? ORDER BY timestamp DESC LIMIT ?",
                    (project_id, limit),
                )
            else:
                cursor = conn.execute(
                    "SELECT * FROM evaluation_runs ORDER BY timestamp DESC LIMIT ?",
                    (limit,),
                )
            return [dict(row) for row in cursor.fetchall()]

    def get_evaluation_results_for_run(self, run_id: str, project_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Returns all individual results for a run, optionally verifying parent run project ownership."""
        with self.get_connection() as conn:
            if project_id:
                run_check = conn.execute(
                    "SELECT 1 FROM evaluation_runs WHERE run_id = ? AND project_id = ?",
                    (run_id, project_id),
                ).fetchone()
                if not run_check:
                    return []
            cursor = conn.execute(
                "SELECT * FROM evaluation_results WHERE run_id = ? ORDER BY result_id",
                (run_id,),
            )
            return [dict(row) for row in cursor.fetchall()]

    # -------------------------------------------------------------------------
    # Canonical Trace & Span Persistence (Milestone 2 - Phase 1)
    # -------------------------------------------------------------------------

    def create_trace(self, trace: Trace, project_id: Optional[str] = None) -> None:
        """Persists a new trace record. Fails with IntegrityError if trace_id already exists."""
        pid = project_id or getattr(trace, "project_id", None)
        with self.get_connection() as conn:
            if not pid and trace.run_id:
                r = conn.execute("SELECT project_id FROM evaluation_runs WHERE run_id = ?", (trace.run_id,)).fetchone()
                if r and r[0]:
                    pid = r[0]
            pid = pid or "default"
            conn.execute(
                """
                INSERT INTO traces (
                    trace_id, run_id, case_id, target_id, session_id, name, status,
                    start_time, end_time, attributes_json, schema_version, source, source_ref, created_at, project_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                    pid,
                ),
            )
            if trace.spans:
                self._insert_spans_with_conn(conn, trace.spans)
            conn.commit()

    def save_trace(self, trace: Trace, project_id: Optional[str] = None) -> None:
        """Upserts a trace and any child spans atomically in a single transaction."""
        pid = project_id or getattr(trace, "project_id", None)
        with self.get_connection() as conn:
            if not pid and trace.run_id:
                r = conn.execute("SELECT project_id FROM evaluation_runs WHERE run_id = ?", (trace.run_id,)).fetchone()
                if r and r[0]:
                    pid = r[0]
            pid = pid or "default"
            conn.execute(
                """
                INSERT INTO traces (
                    trace_id, run_id, case_id, target_id, session_id, name, status,
                    start_time, end_time, attributes_json, schema_version, source, source_ref, created_at, project_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                    source_ref=excluded.source_ref,
                    project_id=excluded.project_id
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
                    pid,
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

    def get_trace(self, trace_id: str, include_spans: bool = True, project_id: Optional[str] = None) -> Optional[Trace]:
        """Fetches a trace by ID, optionally filtered by project_id. Optionally populates child spans."""
        with self.get_connection() as conn:
            if project_id:
                cursor = conn.execute("SELECT * FROM traces WHERE trace_id = ? AND project_id = ?", (trace_id, project_id))
            else:
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

    def get_traces_for_run(self, run_id: str, include_spans: bool = False, project_id: Optional[str] = None) -> List[Trace]:
        """Returns all traces associated with a specific evaluation run, optionally filtered by project_id."""
        with self.get_connection() as conn:
            if project_id:
                cursor = conn.execute(
                    "SELECT * FROM traces WHERE run_id = ? AND project_id = ? ORDER BY start_time ASC, created_at ASC",
                    (run_id, project_id),
                )
            else:
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

    def get_traces_for_case(self, run_id: str, case_id: str, include_spans: bool = False, project_id: Optional[str] = None) -> List[Trace]:
        """Returns all traces for a specific run case, optionally filtered by project_id."""
        with self.get_connection() as conn:
            if project_id:
                cursor = conn.execute(
                    "SELECT * FROM traces WHERE run_id = ? AND case_id = ? AND project_id = ? ORDER BY start_time ASC, created_at ASC",
                    (run_id, case_id, project_id),
                )
            else:
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

    def list_traces(self, limit: int = 50, include_spans: bool = False, project_id: Optional[str] = None) -> List[Trace]:
        """Returns the most recent canonical traces across all runs, optionally filtered by project_id."""
        with self.get_connection() as conn:
            if project_id:
                cursor = conn.execute(
                    "SELECT * FROM traces WHERE project_id = ? ORDER BY start_time DESC, created_at DESC LIMIT ?",
                    (project_id, max(1, limit)),
                )
            else:
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

        pid = row["project_id"] if "project_id" in row.keys() and row["project_id"] else "default"
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
            project_id=pid,
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

    # -- API Key Management ----------------------------------------------------

    def create_api_key(
        self,
        key_id: str,
        key_hash: str,
        name: str,
        scopes: List[str],
        project_id: str = "default",
        principal: Optional[str] = None,
        created_at: Optional[str] = None,
        expires_at: Optional[str] = None,
    ) -> None:
        """Stores a hashed API key with assigned scopes and tenant scoping."""
        if created_at is None:
            created_at = datetime.now(timezone.utc).isoformat()
        with self.get_connection() as conn:
            conn.execute(
                """
                INSERT INTO api_keys (key_id, key_hash, name, scopes_json, project_id, principal, created_at, expires_at, revoked)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0)
                """,
                (key_id, key_hash, name, json.dumps(scopes), project_id, principal, created_at, expires_at),
            )
            conn.commit()

    def get_api_key_by_hash(self, key_hash: str) -> Optional[Dict[str, Any]]:
        """Retrieves an active (non-revoked) API key by its SHA-256 hash."""
        with self.get_connection() as conn:
            cur = conn.execute("SELECT * FROM api_keys WHERE key_hash = ? AND revoked = 0", (key_hash,))
            row = cur.fetchone()
            if not row:
                return None
            d = dict(row)
            d["scopes"] = json.loads(d.get("scopes_json") or "[]")
            # Update last_used_at in background
            try:
                conn.execute(
                    "UPDATE api_keys SET last_used_at = ? WHERE key_id = ?",
                    (datetime.now(timezone.utc).isoformat(), d["key_id"]),
                )
                conn.commit()
            except Exception:
                pass
            return d

    def revoke_api_key(self, key_id: str) -> bool:
        """Revokes an API key, rendering it invalid for all scopes."""
        with self.get_connection() as conn:
            cur = conn.execute("UPDATE api_keys SET revoked = 1 WHERE key_id = ?", (key_id,))
            conn.commit()
            return cur.rowcount > 0

    def list_api_keys(self, project_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Lists registered API keys, optionally scoped to a project."""
        with self.get_connection() as conn:
            if project_id:
                cur = conn.execute(
                    "SELECT * FROM api_keys WHERE project_id = ? ORDER BY created_at DESC",
                    (project_id,),
                )
            else:
                cur = conn.execute("SELECT * FROM api_keys ORDER BY created_at DESC")
            keys = []
            for row in cur.fetchall():
                d = dict(row)
                d["scopes"] = json.loads(d.get("scopes_json") or "[]")
                keys.append(d)
            return keys

    # -- Asynchronous Job State Management -------------------------------------

    def get_run_job_by_idempotency_key(self, idempotency_key: str, project_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Retrieves a job by its unique idempotency key, optionally scoped by project."""
        with self.get_connection() as conn:
            if project_id is not None:
                cur = conn.execute(
                    "SELECT * FROM run_jobs WHERE idempotency_key = ? AND project_id = ?",
                    (idempotency_key, project_id),
                )
            else:
                cur = conn.execute(
                    "SELECT * FROM run_jobs WHERE idempotency_key = ?",
                    (idempotency_key,),
                )
            row = cur.fetchone()
            return dict(row) if row else None

    def create_run_job(
        self,
        job_id: str,
        plan_id: str,
        status: str = "queued",
        total_cases: int = 0,
        run_id: Optional[str] = None,
        project_id: str = "default",
        requested_by_key_id: Optional[str] = None,
        worker_id: Optional[str] = None,
        lease_expires_at: Optional[str] = None,
        heartbeat_at: Optional[str] = None,
        attempt_count: int = 0,
        idempotency_key: Optional[str] = None,
        requested_by: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """Records a new asynchronous benchmark execution job.

        Idempotent: if idempotency_key is provided and already exists, returns the existing job.
        """
        if idempotency_key:
            existing = self.get_run_job_by_idempotency_key(idempotency_key, project_id=project_id)
            if existing:
                return existing

        now = datetime.now(timezone.utc).isoformat()
        with self.get_connection() as conn:
            cols = {r[1] for r in conn.execute("PRAGMA table_info(run_jobs)").fetchall()}
            insert_cols = [
                "job_id",
                "plan_id",
                "run_id",
                "status",
                "total_cases",
                "completed_cases",
                "failed_cases",
                "booked_spend_usd",
                "error_message",
                "cancelled",
                "created_at",
                "updated_at",
                "finished_at",
                "project_id",
                "requested_by_key_id",
                "worker_id",
                "lease_expires_at",
                "heartbeat_at",
                "attempt_count",
            ]
            insert_vals: List[Any] = [
                job_id,
                plan_id,
                run_id,
                status,
                total_cases,
                0,
                0,
                None,
                None,
                0,
                now,
                now,
                None,
                project_id,
                requested_by_key_id,
                worker_id,
                lease_expires_at,
                heartbeat_at,
                attempt_count,
            ]
            if "idempotency_key" in cols:
                insert_cols.append("idempotency_key")
                insert_vals.append(idempotency_key)
            if "requested_by" in cols:
                insert_cols.append("requested_by")
                insert_vals.append(requested_by or requested_by_key_id)

            placeholders = ", ".join(["?"] * len(insert_vals))
            sql = f"INSERT INTO run_jobs ({', '.join(insert_cols)}) VALUES ({placeholders})"
            try:
                conn.execute(sql, insert_vals)
                conn.commit()
            except sqlite3.IntegrityError:
                if idempotency_key:
                    existing = self.get_run_job_by_idempotency_key(idempotency_key, project_id=project_id)
                    if existing:
                        return existing
                raise
        return self.get_run_job(job_id, project_id=project_id)

    def update_run_job(
        self,
        job_id: str,
        status: Optional[str] = None,
        run_id: Optional[str] = None,
        completed_cases: Optional[int] = None,
        failed_cases: Optional[int] = None,
        booked_spend_usd: Optional[str] = None,
        error_message: Optional[str] = None,
        finished_at: Optional[str] = None,
        cancelled: Optional[bool] = None,
        worker_id: Optional[str] = None,
        lease_expires_at: Optional[str] = None,
        heartbeat_at: Optional[str] = None,
        attempt_count: Optional[int] = None,
        started_at: Optional[str] = None,
        cancelled_at: Optional[str] = None,
        expected_worker_id: Optional[str] = None,
    ) -> bool:
        """Updates progress, status, or spend for a running/completed execution job."""
        now = datetime.now(timezone.utc).isoformat()
        updates = ["updated_at = ?"]
        params: List[Any] = [now]
        if status is not None:
            updates.append("status = ?")
            params.append(status)
        if run_id is not None:
            updates.append("run_id = ?")
            params.append(run_id)
        if completed_cases is not None:
            updates.append("completed_cases = ?")
            params.append(completed_cases)
        if failed_cases is not None:
            updates.append("failed_cases = ?")
            params.append(failed_cases)
        if booked_spend_usd is not None:
            updates.append("booked_spend_usd = ?")
            params.append(booked_spend_usd)
        if error_message is not None:
            updates.append("error_message = ?")
            params.append(error_message)
        if finished_at is not None:
            updates.append("finished_at = ?")
            params.append(finished_at)
        if cancelled is not None:
            updates.append("cancelled = ?")
            params.append(1 if cancelled else 0)
        if worker_id is not None:
            updates.append("worker_id = ?")
            params.append(worker_id)
        if lease_expires_at is not None:
            updates.append("lease_expires_at = ?")
            params.append(lease_expires_at)
        if heartbeat_at is not None:
            updates.append("heartbeat_at = ?")
            params.append(heartbeat_at)
        if attempt_count is not None:
            updates.append("attempt_count = ?")
            params.append(attempt_count)
        if started_at is not None:
            updates.append("started_at = ?")
            params.append(started_at)
        if cancelled_at is not None:
            updates.append("cancelled_at = ?")
            params.append(cancelled_at)
        where_clause = "WHERE job_id = ?"
        params.append(job_id)
        if expected_worker_id is not None:
            where_clause += " AND (worker_id IS NULL OR worker_id = ?)"
            params.append(expected_worker_id)
        with self.get_connection() as conn:
            cur = conn.execute(f"UPDATE run_jobs SET {', '.join(updates)} {where_clause}", params)
            conn.commit()
            return cur.rowcount > 0

    def claim_run_job(self, job_id: str, worker_id: str, lease_duration_s: int = 60) -> bool:
        """Atomically claims a queued or expired job for execution by worker_id."""
        now_dt = datetime.now(timezone.utc)
        now_str = now_dt.isoformat()
        lease_expiry = (now_dt + timedelta(seconds=lease_duration_s)).isoformat()
        with self.get_connection() as conn:
            cur = conn.execute(
                """
                UPDATE run_jobs
                SET status = 'running',
                    worker_id = ?,
                    started_at = COALESCE(started_at, ?),
                    heartbeat_at = ?,
                    lease_expires_at = ?,
                    attempt_count = attempt_count + 1,
                    updated_at = ?
                WHERE job_id = ?
                  AND cancelled = 0
                  AND (
                      status = 'queued'
                      OR (status IN ('queued', 'running', 'claimed') AND lease_expires_at IS NOT NULL AND lease_expires_at < ?)
                  )
                """,
                (worker_id, now_str, now_str, lease_expiry, now_str, job_id, now_str),
            )
            conn.commit()
            return cur.rowcount == 1

    def renew_job_lease(self, job_id: str, worker_id: str, lease_duration_s: int = 60) -> bool:
        """Extends worker heartbeat and lease while job is actively running."""
        now_dt = datetime.now(timezone.utc)
        now_str = now_dt.isoformat()
        lease_expiry = (now_dt + timedelta(seconds=lease_duration_s)).isoformat()
        with self.get_connection() as conn:
            cur = conn.execute(
                """
                UPDATE run_jobs
                SET heartbeat_at = ?,
                    lease_expires_at = ?,
                    updated_at = ?
                WHERE job_id = ?
                  AND worker_id = ?
                  AND cancelled = 0
                  AND status = 'running'
                """,
                (now_str, lease_expiry, now_str, job_id, worker_id),
            )
            conn.commit()
            return cur.rowcount == 1

    def recover_stale_jobs(self, grace_period_s: int = 0) -> List[str]:
        """Detects jobs whose worker leases expired without heartbeat renewal and reconciles them.

        Healthy workers actively executing with unexpired leases are never interrupted.
        """
        now_dt = datetime.now(timezone.utc)
        cutoff = (now_dt - timedelta(seconds=grace_period_s)).isoformat()
        now_str = now_dt.isoformat()
        recovered_ids: List[str] = []
        with self.get_connection() as conn:
            cur = conn.execute(
                """
                SELECT job_id, plan_id, run_id, cancelled FROM run_jobs
                WHERE status IN ('running', 'claimed')
                  AND (lease_expires_at IS NULL OR lease_expires_at < ?)
                """,
                (cutoff,),
            )
            rows = cur.fetchall()
            for row in rows:
                jid = row["job_id"]
                pid = row["plan_id"]
                rid = row["run_id"]
                was_cancelled = bool(row["cancelled"])
                new_status = "cancelled" if was_cancelled else "failed"
                err = "Execution was cancelled." if was_cancelled else "Execution interrupted: worker lease expired without heartbeat renewal (worker lost)."
                conn.execute(
                    """
                    UPDATE run_jobs
                    SET status = ?,
                        error_message = ?,
                        finished_at = ?,
                        updated_at = ?
                    WHERE job_id = ? AND status IN ('running', 'claimed')
                    """,
                    (new_status, err, now_str, now_str, jid),
                )
                if rid:
                    conn.execute("DELETE FROM budget_reservations WHERE run_id = ?", (rid,))
                if pid:
                    conn.execute("DELETE FROM budget_reservations WHERE plan_id = ?", (pid,))
                recovered_ids.append(jid)
            conn.commit()
        return recovered_ids

    def request_job_cancellation(self, job_id: str, project_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Atomically signals cancellation for a job across processes."""
        now_str = datetime.now(timezone.utc).isoformat()
        with self.get_connection() as conn:
            if project_id:
                cur = conn.execute("SELECT * FROM run_jobs WHERE job_id = ? AND project_id = ?", (job_id, project_id))
            else:
                cur = conn.execute("SELECT * FROM run_jobs WHERE job_id = ?", (job_id,))
            row = cur.fetchone()
            if not row:
                return None

            current_status = row["status"]
            if current_status in ("completed", "failed", "interrupted"):
                d = dict(row)
                d["cancelled"] = bool(d.get("cancelled"))
                return d

            if current_status == "queued":
                conn.execute(
                    """
                    UPDATE run_jobs
                    SET cancelled = 1,
                        cancelled_at = ?,
                        status = 'cancelled',
                        finished_at = ?,
                        updated_at = ?
                    WHERE job_id = ?
                    """,
                    (now_str, now_str, now_str, job_id),
                )
            else:
                conn.execute(
                    """
                    UPDATE run_jobs
                    SET cancelled = 1,
                        cancelled_at = ?,
                        updated_at = ?
                    WHERE job_id = ?
                    """,
                    (now_str, now_str, job_id),
                )
            conn.commit()

        return self.get_run_job(job_id, project_id=project_id)

    def get_run_job(self, job_id: str, project_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Retrieves execution job state by ID, optionally filtered by project_id."""
        with self.get_connection() as conn:
            if project_id:
                cur = conn.execute("SELECT * FROM run_jobs WHERE job_id = ? AND project_id = ?", (job_id, project_id))
            else:
                cur = conn.execute("SELECT * FROM run_jobs WHERE job_id = ?", (job_id,))
            row = cur.fetchone()
            if not row:
                return None
            d = dict(row)
            d["cancelled"] = bool(d.get("cancelled"))
            return d

    def list_run_jobs(self, limit: int = 50, project_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Lists recent execution jobs, optionally filtered by project_id."""
        with self.get_connection() as conn:
            if project_id:
                cur = conn.execute(
                    "SELECT * FROM run_jobs WHERE project_id = ? ORDER BY created_at DESC LIMIT ?",
                    (project_id, max(1, limit)),
                )
            else:
                cur = conn.execute("SELECT * FROM run_jobs ORDER BY created_at DESC LIMIT ?", (max(1, limit),))
            results = []
            for r in cur.fetchall():
                d = dict(r)
                d["cancelled"] = bool(d.get("cancelled"))
                results.append(d)
            return results

    # -- Multi-Tenant Organization & Project Management -----------------------

    def create_organization(self, org_id: str, name: str, created_at: Optional[str] = None) -> Dict[str, Any]:
        """Creates an organization tenant."""
        if created_at is None:
            created_at = datetime.now(timezone.utc).isoformat()
        with self.get_connection() as conn:
            conn.execute(
                "INSERT INTO organizations (org_id, name, created_at) VALUES (?, ?, ?)",
                (org_id, name, created_at),
            )
            conn.commit()
        return {"org_id": org_id, "name": name, "created_at": created_at}

    def get_organization(self, org_id: str) -> Optional[Dict[str, Any]]:
        """Fetches organization by ID."""
        with self.get_connection() as conn:
            row = conn.execute("SELECT * FROM organizations WHERE org_id = ?", (org_id,)).fetchone()
            return dict(row) if row else None

    def list_organizations(self) -> List[Dict[str, Any]]:
        """Lists all organizations."""
        with self.get_connection() as conn:
            return [dict(r) for r in conn.execute("SELECT * FROM organizations ORDER BY created_at ASC").fetchall()]

    def create_project(
        self,
        project_id: str,
        org_id: str,
        name: str,
        settings: Optional[Dict[str, Any]] = None,
        created_at: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Creates a project scoped to an organization."""
        if created_at is None:
            created_at = datetime.now(timezone.utc).isoformat()
        settings_json = json.dumps(settings or {})
        with self.get_connection() as conn:
            conn.execute(
                "INSERT INTO projects (project_id, org_id, name, settings_json, created_at) VALUES (?, ?, ?, ?, ?)",
                (project_id, org_id, name, settings_json, created_at),
            )
            conn.commit()
        return {
            "project_id": project_id,
            "org_id": org_id,
            "name": name,
            "settings": settings or {},
            "created_at": created_at,
        }

    def get_project(self, project_id: str) -> Optional[Dict[str, Any]]:
        """Fetches project by ID."""
        with self.get_connection() as conn:
            row = conn.execute("SELECT * FROM projects WHERE project_id = ?", (project_id,)).fetchone()
            if not row:
                return None
            d = dict(row)
            d["settings"] = json.loads(d.get("settings_json") or "{}")
            return d

    def update_project_settings(self, project_id: str, settings: Dict[str, Any]) -> None:
        """Updates project configuration settings."""
        with self.get_connection() as conn:
            conn.execute(
                "UPDATE projects SET settings_json = ? WHERE project_id = ?",
                (json.dumps(settings), project_id),
            )
            conn.commit()

    def list_projects(self, org_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Lists projects, optionally filtered by organization."""
        with self.get_connection() as conn:
            if org_id:
                cur = conn.execute("SELECT * FROM projects WHERE org_id = ? ORDER BY created_at ASC", (org_id,))
            else:
                cur = conn.execute("SELECT * FROM projects ORDER BY created_at ASC")
            results = []
            for r in cur.fetchall():
                d = dict(r)
                d["settings"] = json.loads(d.get("settings_json") or "{}")
                results.append(d)
            return results

    def add_membership(
        self,
        membership_id: str,
        user_id: str,
        project_id: str,
        role: str,
        created_at: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Assigns a user to a project with a specific RBAC role."""
        if created_at is None:
            created_at = datetime.now(timezone.utc).isoformat()
        with self.get_connection() as conn:
            conn.execute(
                "INSERT INTO memberships (membership_id, user_id, project_id, role, created_at) VALUES (?, ?, ?, ?, ?)",
                (membership_id, user_id, project_id, role.lower(), created_at),
            )
            conn.commit()
        return {
            "membership_id": membership_id,
            "user_id": user_id,
            "project_id": project_id,
            "role": role.lower(),
            "created_at": created_at,
        }

    def get_membership(self, user_id: str, project_id: str) -> Optional[Dict[str, Any]]:
        """Gets membership record for a user within a project."""
        with self.get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM memberships WHERE user_id = ? AND project_id = ?",
                (user_id, project_id),
            ).fetchone()
            return dict(row) if row else None

    def list_memberships(self, project_id: str) -> List[Dict[str, Any]]:
        """Lists all memberships for a project."""
        with self.get_connection() as conn:
            rows = conn.execute("SELECT * FROM memberships WHERE project_id = ? ORDER BY created_at ASC", (project_id,)).fetchall()
            return [dict(r) for r in rows]

    # -- Append-Only Audit Log -------------------------------------------------

    def record_audit_event(
        self,
        audit_id: str,
        project_id: str,
        principal: str,
        action: str,
        resource_type: Optional[str] = None,
        resource_id: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        created_at: Optional[str] = None,
    ) -> None:
        """Appends an event to the immutable audit log with automatic secret scrubbing."""
        from runport.providers.base import scrub_secrets

        if created_at is None:
            created_at = datetime.now(timezone.utc).isoformat()
        clean_details = scrub_secrets(details or {})
        with self.get_connection() as conn:
            conn.execute(
                """
                INSERT INTO audit_log (audit_id, project_id, principal, action, resource_type, resource_id, details_json, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (audit_id, project_id, principal, action, resource_type, resource_id, json.dumps(clean_details), created_at),
            )
            conn.commit()

    def list_audit_logs(self, project_id: str, limit: int = 100) -> List[Dict[str, Any]]:
        """Lists audit log records for a project in reverse chronological order."""
        with self.get_connection() as conn:
            cur = conn.execute(
                "SELECT * FROM audit_log WHERE project_id = ? ORDER BY created_at DESC LIMIT ?",
                (project_id, max(1, limit)),
            )
            results = []
            for r in cur.fetchall():
                d = dict(r)
                d["details"] = json.loads(d.get("details_json") or "{}")
                results.append(d)
            return results

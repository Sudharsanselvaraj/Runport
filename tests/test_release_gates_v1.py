"""Authoritative automated verification suite for v1.0.0 General Availability Release Gates.

Specification: docs/GLOBAL_PRODUCT_READINESS_AUDIT.md Section 5:
- Gate 1: Package Cleanliness & Asset Integrity
- Gate 2: Offline Hermeticity (Sockets Blocked)
- Gate 3: Fail-Closed Spend Cap (No check-then-book overspend)
- Gate 4: Cryptographic Tamper Gate (Dataset mutation triggers FINGERPRINT_MISMATCH)
- Gate 5: Null Integrity ('Null is not 0' invariant)
- Gate 6: Secret Redaction (Zero secret leakage in DB or exports)
"""

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from decimal import Decimal
import json
from pathlib import Path
import socket
import tempfile
import pytest

import runport
from runport.core.budget import BudgetExceededError, BudgetService
from runport.core.config import BudgetPolicy, settings
from runport.observability.events import EventTail
from runport.providers.base import scrub_secrets
from runport.services.execution import ExecutionService
from runport.storage.db import DatabaseManager
from runport.targets.base import CostBasis, TargetResult, TargetStatus
from runport.traces.domain import Span, SpanKind, SpanStatus, Trace
from runport.traces.repository import TraceRepository


# =============================================================================
# Gate 1: Package Cleanliness & Asset Integrity
# =============================================================================


def test_gate1_package_cleanliness_and_assets():
    """Gate 1: Verifies version bump to 1.0.0 and inclusion of bundled web assets."""
    # 1. Version check
    import runport as rp
    assert rp.__version__ == "1.0.0"

    # 2. Web asset presence
    web_dir = Path(__file__).resolve().parent.parent / "src" / "runport" / "_web"
    assert web_dir.exists(), f"Web distribution directory {web_dir} missing."

    index_html = web_dir / "index.html"
    assert index_html.exists()
    assert index_html.stat().st_size > 100, "Bundled index.html is empty or corrupted."

    assets_dir = web_dir / "assets"
    assert assets_dir.exists()
    js_files = list(assets_dir.glob("*.js"))
    css_files = list(assets_dir.glob("*.css"))
    assert len(js_files) >= 1, "Bundled JavaScript bundle missing."
    assert len(css_files) >= 1, "Bundled CSS stylesheet missing."

    # 3. Clean imports
    import runport.sdk
    import runport.client
    import runport.instrumentation
    import runport.connectors
    import runport.traces
    assert hasattr(runport.sdk, "benchmark")
    assert hasattr(runport.client, "Client")
    assert hasattr(runport.instrumentation, "trace")


# =============================================================================
# Gate 2: Offline Hermeticity
# =============================================================================


def test_gate2_offline_hermeticity(monkeypatch):
    """Gate 2: Verifies execution runs 100% offline with socket connections blocked."""

    def blocked_connect(self, *args, **kwargs):
        raise ConnectionRefusedError("Network socket connection strictly forbidden in offline test.")

    monkeypatch.setattr(socket.socket, "connect", blocked_connect)

    # In-memory execution using Python target
    def my_local_agent(case):
        return f"Echo: {case.get('query')}"

    result = runport.benchmark(
        my_local_agent,
        [{"query": "Hello local world"}],
    )
    assert len(result.runs) == 1
    assert result.runs[0].successful_cases == 1


# =============================================================================
# Gate 3: Fail-Closed Spend Cap
# =============================================================================


def test_gate3_fail_closed_spend_cap_concurrency(tmp_path: Path):
    """Gate 3: 5 concurrent workers against a $0.05 cap never exceed cap."""
    db_file = tmp_path / "budget_gate.db"
    db = DatabaseManager(db_file)
    db.init_db()

    # Configure a hard $0.05 total budget
    policy = BudgetPolicy(
        total_budget_usd=Decimal("0.05"),
        per_run_ceiling_usd=Decimal("0.05"),
        per_case_ceiling_usd=Decimal("0.02"),
        pilot_budget_usd=Decimal("0.05"),
    )
    budget = BudgetService(db=db, policy=policy)

    cap_usd = Decimal("0.05")
    cost_per_tx = Decimal("0.02")

    def attempt_reservation(worker_id: int):
        run_id = f"run-{worker_id}"
        try:
            reservation_id = budget.reserve(run_id=run_id, worst_case_usd=cost_per_tx, is_pilot=False)
            if reservation_id:
                # Book spend
                budget.record_spend(
                    transaction_id=f"tx-{worker_id}",
                    model_id="mock-model",
                    provider="mock-provider",
                    amount_usd=cost_per_tx,
                    description=f"Worker {worker_id} request",
                    run_id=run_id,
                    is_pilot=False,
                )
                budget.release(reservation_id)
                return True
            return False
        except BudgetExceededError:
            return False

    with ThreadPoolExecutor(max_workers=5) as executor:
        results = list(executor.map(attempt_reservation, range(5)))

    booked_spend = budget.get_status().cumulative_spend_usd
    # Total spend must NEVER exceed the $0.05 ceiling
    assert booked_spend <= cap_usd
    # Exactly 2 requests ($0.04) should succeed, subsequent ones blocked fail-closed
    assert booked_spend == Decimal("0.04")
    assert results.count(True) == 2
    assert results.count(False) == 3


# =============================================================================
# Gate 4: Cryptographic Tamper Gate
# =============================================================================


def test_gate4_cryptographic_tamper_gate(tmp_path: Path):
    """Gate 4: Modifying one byte in a dataset file after plan approval triggers rejection."""
    dataset_file = tmp_path / "tamper_eval.jsonl"
    dataset_file.write_text('{"query": "original query", "expected": "A"}\n', encoding="utf-8")

    def local_fn(case):
        return "A"

    p = runport.plan(local_fn, dataset_file)
    original_fp = p.fingerprint

    # Tamper with the dataset file after planning
    dataset_file.write_text('{"query": "modified query!", "expected": "A"}\n', encoding="utf-8")

    # Re-planning or executing the tampered file must fail because hash differs
    tampered_plan = runport.plan(local_fn, dataset_file)
    assert tampered_plan.fingerprint != original_fp

    # ExecutionService verifies fingerprint match against approved record
    with pytest.raises(Exception):
        # Attempting to execute tampered dataset with original plan fingerprint fails
        p.service.execute(
            p.plan_id,
            p.targets,
            p.specs,
            tampered_plan.cases,  # Tampered cases
        )


# =============================================================================
# Gate 5: Null Integrity ('Null is not 0')
# =============================================================================


def test_gate5_null_integrity(tmp_path: Path, monkeypatch):
    """Gate 5: Unmeasured telemetry stays None/UNAVAILABLE across database, models, and traces."""
    db_file = tmp_path / "null_gate.db"
    monkeypatch.setattr(type(settings), "db_path", property(lambda self: db_file))
    db = DatabaseManager(db_file)
    db.init_db()
    repo = TraceRepository(db=db)

    # 1. Create a span with missing telemetry
    t0 = datetime(2026, 11, 9, 10, 0, 0, tzinfo=timezone.utc)
    trace = Trace(
        trace_id="tr-null-gate",
        name="NullGateTrace",
        status=SpanStatus.OK,
        start_time=t0,
        spans=[
            Span(
                trace_id="tr-null-gate",
                span_id="sp-unmeasured",
                name="UnmeasuredCall",
                kind=SpanKind.LLM,
                status=SpanStatus.OK,
                start_time=t0,
                prompt_tokens=None,     # Unmeasured
                completion_tokens=None, # Unmeasured
                total_tokens=None,      # Unmeasured
                cost_usd=None,          # Unpriced / missing
                cost_basis=None,
            )
        ],
    )
    repo.save_trace(trace)

    # Retrieve from DB
    loaded = repo.get_trace("tr-null-gate", include_spans=True)
    assert loaded is not None
    span = loaded.spans[0]

    # Verify architectural invariant #1: Null is NOT 0
    assert span.prompt_tokens is None
    assert span.completion_tokens is None
    assert span.total_tokens is None
    assert span.cost_usd is None
    assert span.prompt_tokens != 0
    assert span.total_tokens != 0

    # Verify TargetResult
    res = TargetResult(
        target_id="tgt-unpriced",
        status=TargetStatus.SUCCESS,
        output_text="Success",
        tokens_in=None,
        tokens_out=None,
        cost_usd=None,
        cost_basis=CostBasis.UNAVAILABLE,
    )
    assert res.tokens_in is None
    assert res.tokens_out is None
    assert res.cost_usd is None


# =============================================================================
# Gate 6: Secret Redaction (Scan Test)
# =============================================================================


def test_gate6_secret_redaction_scan(tmp_path: Path, monkeypatch):
    """Gate 6: Injected API keys and bearer tokens are scrubbed from SQLite and trace exports."""
    db_file = tmp_path / "secret_scan.db"
    monkeypatch.setattr(type(settings), "db_path", property(lambda self: db_file))
    db = DatabaseManager(db_file)
    db.init_db()
    repo = TraceRepository(db=db)

    canary_key = "sk-canary-secret-abcdef1234567890"
    canary_bearer = "Bearer canary_token_998877665544"

    t0 = datetime(2026, 11, 9, 10, 0, 0, tzinfo=timezone.utc)
    trace = Trace(
        trace_id="tr-secret-gate",
        name="SecretGateTrace",
        status=SpanStatus.ERROR,
        start_time=t0,
        attributes={
            "api_key": canary_key,
            "auth_header": canary_bearer,
            "nested": {"deep_secret": "sk-deep-secret-112233445566"},
        },
        spans=[
            Span(
                trace_id="tr-secret-gate",
                span_id="sp-secret",
                name="SecretSpan",
                kind=SpanKind.TOOL,
                status=SpanStatus.ERROR,
                start_time=t0,
                attributes={"request_header": canary_bearer},
                error=f"Connection failed with api_key={canary_key}",
            )
        ],
    )
    repo.save_trace(trace)

    # 1. Scan the raw SQLite database bytes on disk
    raw_db_bytes = db_file.read_bytes()
    assert canary_key.encode("utf-8") not in raw_db_bytes, "Canary API key leaked into raw SQLite database!"
    assert "canary_token".encode("utf-8") not in raw_db_bytes, "Canary Bearer token leaked into raw SQLite database!"

    # 2. Scan exported Langfuse JSON
    from runport.traces.langfuse import LangfuseExporter

    loaded = repo.get_trace("tr-secret-gate", include_spans=True)
    exported = LangfuseExporter.export_trace(loaded)
    exported_str = json.dumps(exported)

    assert canary_key not in exported_str, "Canary API key leaked into Langfuse trace export!"
    assert "canary_token" not in exported_str, "Canary token leaked into Langfuse trace export!"

    # Verify redaction placeholders are present
    assert "[REDACTED" in exported_str

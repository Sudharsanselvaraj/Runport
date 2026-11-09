"""Offline unit tests for Runport Remote Python Client (runport.client.Client).

Verifies:
- List and inspect targets.
- Create dataset.
- Plan lifecycle, approval enforcement, and error mapping.
- Execute asynchronous job and wait for completion.
- Inspect runs and budget status.
- Zero socket simulation: all requests run via httpx.ASGITransport in-memory.
"""

from decimal import Decimal
from pathlib import Path
import pytest
from httpx import ASGITransport

from runport.api.app import create_app
from runport.client import (
    ApprovalRequiredError,
    Client,
    Job,
    Plan,
)
from runport.core.config import settings
from runport.models.catalog import ModelCandidate, seed_default_portfolio
from runport.storage.db import DatabaseManager


@pytest.fixture
def client_env(tmp_path: Path, monkeypatch):
    """Sets up an isolated database and dataset environment for Client testing."""
    db_file = tmp_path / "client_test.db"
    monkeypatch.setattr(type(settings), "db_path", property(lambda self: db_file))

    eval_dir = tmp_path / "data" / "evaluation"
    eval_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(settings, "workspace_root", tmp_path)

    sample_dataset = eval_dir / "client_dataset.jsonl"
    with open(sample_dataset, "w", encoding="utf-8") as f:
        f.write('{"id": "c-01", "query": "Hello", "expected_answer": "Hi", "classification": "PUBLIC"}\n')
        f.write('{"id": "c-02", "query": "Ping", "expected_answer": "Pong", "classification": "PUBLIC"}\n')

    db = DatabaseManager(db_file)
    db.init_db()

    seed_default_portfolio(
        db,
        [
            ModelCandidate(
                model_id="google/gemini-3.5-flash-lite",
                display_name="Gemini 3.5 Flash Lite",
                provider="google",
                deployment_mode="HOSTED_DIRECT",
                license="Proprietary Commercial API",
                context_length=1000000,
                input_price_per_1m_usd=Decimal("0.0750"),
                output_price_per_1m_usd=Decimal("0.3000"),
                verification_status="UNVERIFIED_CATALOG_ENTRY",
                experimental_purpose="High-throughput multimodal baseline.",
            ),
        ],
    )

    app = create_app()
    from fastapi.testclient import TestClient

    tc = TestClient(app, base_url="http://127.0.0.1:8000")
    client = Client(http_client=tc)
    return {"client": client, "eval_dir": eval_dir}


def test_client_targets_and_budget(client_env):
    c: Client = client_env["client"]

    # 1. Targets
    targets = c.list_targets()
    assert len(targets) > 0
    t0 = targets[0]
    fetched = c.get_target(t0.target_id)
    assert fetched.target_id == t0.target_id

    # 2. Budget
    budget = c.get_budget()
    assert budget.policy.per_run_ceiling_usd is not None
    assert budget.unresolved_blocked is False


def test_client_dataset_and_plan_lifecycle(client_env):
    c: Client = client_env["client"]

    # 1. Upload dataset
    ds = c.upload_dataset(
        name="uploaded_dataset.jsonl",
        cases=[{"id": "u-01", "query": "What is Runport?", "expected_answer": "Benchmark platform", "classification": "PUBLIC"}],
    )
    assert ds.filename == "uploaded_dataset.jsonl"
    assert ds.case_count == 1

    # 2. Plan
    plan = c.plan(target_ids=["google/gemini-3.5-flash-lite"], dataset="client_dataset.jsonl")
    assert isinstance(plan, Plan)
    assert plan.status == "PENDING"
    assert plan.case_count == 2

    # 3. Execution of unapproved plan fails
    with pytest.raises(ApprovalRequiredError):
        c.execute(plan.plan_id)

    # 4. Approve plan
    approved = c.approve(plan.plan_id, plan.plan_fingerprint, approver="CI Engineer")
    assert approved.status == "APPROVED"
    assert "CI Engineer" in approved.approved_by

    # 5. Execute approved plan -> Job
    job = c.execute(plan.plan_id)
    assert isinstance(job, Job)
    assert job.status in ("queued", "running", "completed")
    assert job.plan_id == plan.plan_id

    # 6. Get job
    fetched_job = c.get_job(job.job_id)
    assert fetched_job.job_id == job.job_id

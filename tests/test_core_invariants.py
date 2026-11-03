"""Tests for core invariants:
1. Unknown-price models run with UNAVAILABLE estimate and require max_cost_per_case_usd.
2. Token approver rejects mismatched fingerprint and consumed approval cannot be reused.
3. API keys are never read from YAML files.
4. Workspace paths do not depend on CWD.
5. DB columns for accuracy and tokens are nullable (additive migration).
"""

from decimal import Decimal
from pathlib import Path
import pytest

from runport.core.approvers import TokenApprover
from runport.core.budget import BudgetExceededError, BudgetService
from runport.core.config import BudgetPolicy
from runport.core.workspace import (
    BudgetConfig,
    StorageConfig,
    WorkspaceConfig,
    load_workspace_config,
)
from runport.providers.base import LiveNotAuthorizedError
from runport.runs.executor import GenericRunner
from runport.runs.planner import ExecutionPlan
from runport.storage.db import DatabaseManager
from runport.targets.base import CostBasis, Target, TargetPricing, TargetResult, TargetStatus, TargetType


class MockUnknownPriceTarget(Target):
    def __init__(self, target_id: str = "unpriced-model"):
        super().__init__(
            target_id=target_id,
            name="Unpriced Model",
            target_type=TargetType.RAW_MODEL,
            pricing=None,  # Unknown / unpriced
        )

    def execute(self, input_payload, context=None):
        return TargetResult(
            target_id=self.target_id,
            status=TargetStatus.SUCCESS,
            output_text="Response from unpriced model",
            latency_ms=45.0,
            tokens_in=None,  # Null is not 0
            tokens_out=None,
            cost_usd=None,
            cost_basis=CostBasis.UNAVAILABLE,
            provenance="LIVE",
        )


def test_unknown_price_model_runs_with_unavailable_estimate_and_requires_per_case_cap(tmp_path):
    """Unknown-price model runs with UNAVAILABLE estimate and requires max_cost_per_case_usd."""
    db = DatabaseManager(tmp_path / "test.db")
    db.init_db()

    # Case 1: require_priced is enabled -> fails preflight
    ws_strict = WorkspaceConfig(
        budget=BudgetConfig(require_priced=True, per_case_usd=Decimal("0.05"))
    )
    runner_strict = GenericRunner(
        budget_service=BudgetService(db=db, policy=ws_strict.budget.to_budget_policy()),
        db=db,
        workspace=ws_strict,
    )
    plan = ExecutionPlan(
        plan_id="p1",
        target_ids=["unpriced-model"],
        dataset_path="test.jsonl",
        dataset_hash="hash1",
        total_cases=1,
        budget_cap_usd=Decimal("1.00"),
        is_live=True,
    )
    target = MockUnknownPriceTarget()
    approver = TokenApprover(token=plan.fingerprint, enabled=True)

    with pytest.raises(BudgetExceededError, match="unknown pricing and require_priced is enabled"):
        runner_strict.execute_plan(plan, {"unpriced-model": target}, [{"id": 1, "input": "hi"}], approver=approver)

    # Case 2: require_priced is false but per_case_usd is zero -> fails because unpriced requires max_cost_per_case_usd
    ws_no_cap = WorkspaceConfig(
        budget=BudgetConfig(require_priced=False, per_case_usd=Decimal("0.00"))
    )
    runner_no_cap = GenericRunner(
        budget_service=BudgetService(db=db, policy=ws_no_cap.budget.to_budget_policy()),
        db=db,
        workspace=ws_no_cap,
    )
    approver2 = TokenApprover(token=plan.fingerprint, enabled=True)
    with pytest.raises(BudgetExceededError, match="requires a positive per-case spend cap"):
        runner_no_cap.execute_plan(plan, {"unpriced-model": target}, [{"id": 1, "input": "hi"}], approver=approver2)

    # Case 3: require_priced is false and positive per_case_usd -> runs with UNAVAILABLE estimate
    ws_ok = WorkspaceConfig(
        budget=BudgetConfig(require_priced=False, per_case_usd=Decimal("0.05"))
    )
    runner_ok = GenericRunner(
        budget_service=BudgetService(db=db, policy=ws_ok.budget.to_budget_policy()),
        db=db,
        workspace=ws_ok,
    )
    approver3 = TokenApprover(token=plan.fingerprint, enabled=True)
    results = runner_ok.execute_plan(plan, {"unpriced-model": target}, [{"id": 1, "input": "hi"}], approver=approver3)
    assert len(results) == 1
    assert results[0].successful_cases == 1
    assert results[0].case_results[0].cost_basis == CostBasis.UNAVAILABLE
    assert results[0].case_results[0].tokens_in is None


def test_token_approver_mismatched_and_consumed_cannot_be_reused():
    """Token approver rejects mismatched fingerprint and consumed approval cannot be reused."""
    fp = "valid-plan-fingerprint-12345"
    approver = TokenApprover(token=fp, enabled=True)

    # Mismatched token rejected
    with pytest.raises(LiveNotAuthorizedError, match="Approval token mismatch"):
        approver.request_approval("different-fingerprint-67890")

    # First consumption succeeds
    decision = approver.request_approval(fp)
    assert decision.approved is True

    # Reusing the consumed token fails
    with pytest.raises(LiveNotAuthorizedError, match="has already been consumed; cannot be reused"):
        approver.request_approval(fp)


def test_api_keys_never_read_from_yaml(tmp_path):
    """API keys, bearer tokens, and secrets in YAML configs are strictly rejected."""
    bad_yaml = tmp_path / "runport.yaml"
    bad_yaml.write_text(
        """
schema_version: "1.0"
name: "leaky-workspace"
targets:
  - id: "custom-api"
    type: "openai_compat"
    options:
      api_key: "sk-live-secret-never-commit-this"
""",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="Secret or API key detected in workspace configuration"):
        load_workspace_config(bad_yaml)

    # Allowed: referencing environment variables
    good_yaml = tmp_path / "runport_good.yaml"
    good_yaml.write_text(
        """
schema_version: "1.0"
name: "clean-workspace"
targets:
  - id: "custom-api"
    type: "openai_compat"
    headers:
      Authorization: "$OPENAI_API_KEY"
""",
        encoding="utf-8",
    )
    cfg = load_workspace_config(good_yaml)
    assert cfg.name == "clean-workspace"


def test_workspace_paths_do_not_depend_on_cwd(tmp_path, monkeypatch):
    """Workspace storage paths anchor to config location, independent of CWD."""
    sub_workspace = tmp_path / "nested" / "project"
    sub_workspace.mkdir(parents=True)
    cfg_file = sub_workspace / "runport.yaml"
    cfg_file.write_text(
        """
schema_version: "1.0"
name: "nested-project"
storage:
  data_dir: "custom_data"
  reports_dir: "custom_reports"
""",
        encoding="utf-8",
    )

    # Change CWD to a completely different location
    other_dir = tmp_path / "somewhere_else"
    other_dir.mkdir()
    monkeypatch.chdir(other_dir)

    cfg = load_workspace_config(cfg_file)
    assert cfg.root_dir == sub_workspace.resolve()
    assert cfg.storage.data_dir == (sub_workspace / "custom_data").resolve()
    assert cfg.storage.reports_dir == (sub_workspace / "custom_reports").resolve()


def test_db_columns_accuracy_and_tokens_nullable(tmp_path):
    """Database columns for accuracy, tokens, and cost allow NULL to uphold 'Null is not 0'."""
    db = DatabaseManager(tmp_path / "nullable_test.db")
    db.init_db()

    run_id = "test-run-null"
    db.save_evaluation_run({
        "run_id": run_id,
        "timestamp": "2026-11-03T00:00:00Z",
        "model_id": "model-1",
        "dataset_path": "data/eval.jsonl",
        "total_cases": 1,
        "completed_cases": 1,
        "failed_cases": 0,
        "total_cost_usd": "0.0000",
        "mean_latency_ms": 12.0,
        "mean_accuracy": 0.0,
        "mean_groundedness": 0.0,
        "mean_overall_score": 0.0,
        "is_dry_run": False,
        "notes": "test",
    })

    # Save results where accuracy and token counts are None (unlabelled / unpriced)
    db.save_evaluation_results([
        {
            "result_id": "res-null-1",
            "run_id": run_id,
            "case_id": "case-1",
            "prompt": "Evaluate this",
            "expected_answer": None,
            "generated_output": "Some response",
            "latency_ms": 25.5,
            "prompt_tokens": None,      # NULL in DB
            "completion_tokens": None,  # NULL in DB
            "cost_usd": None,           # NULL in DB
            "accuracy": None,           # NULL in DB
            "groundedness": None,       # NULL in DB
            "format_adherence": 1.0,
            "overall_score": None,      # NULL in DB
            "evaluator_notes": "Unlabelled case",
        }
    ])

    results = db.get_evaluation_results_for_run(run_id)
    assert len(results) == 1
    row = results[0]
    assert row["prompt_tokens"] is None
    assert row["completion_tokens"] is None
    assert row["cost_usd"] is None
    assert row["accuracy"] is None
    assert row["overall_score"] is None


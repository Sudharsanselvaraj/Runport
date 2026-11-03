"""Unit tests for Workspace configuration, JSON Schema, and runport init."""

import json
from decimal import Decimal
from pathlib import Path
import pytest
from typer.testing import CliRunner

from runport.cli import app
from runport.core.workspace import (
    WorkspaceConfig,
    generate_workspace_schema,
    init_workspace,
    load_workspace_config,
)

runner = CliRunner()


def test_workspace_config_defaults():
    """Verify owner-confirmed budget defaults: total $5, per-run $1, per-case $0.05, require_priced=False."""
    cfg = WorkspaceConfig()
    assert cfg.schema_version == "1.0"
    assert cfg.budget.total_usd == Decimal("5.00")
    assert cfg.budget.per_run_usd == Decimal("1.00")
    assert cfg.budget.per_case_usd == Decimal("0.05")
    assert cfg.budget.pilot_usd == Decimal("1.00")
    assert cfg.budget.require_priced is False
    assert cfg.approver.default_mode == "interactive"
    assert cfg.approver.token_approver_enabled is False
    assert "restricted_user_id" in cfg.telemetry.forbidden_fields


def test_generate_workspace_schema():
    """Workspace configuration exports a valid JSON Schema."""
    schema = generate_workspace_schema()
    assert isinstance(schema, dict)
    assert schema.get("title") == "WorkspaceConfig"
    assert "properties" in schema
    assert "budget" in schema["properties"]
    assert "approver" in schema["properties"]


def test_init_workspace_and_load(tmp_path: Path):
    """init_workspace initializes directory structure and valid runport.yaml."""
    cfg_path = init_workspace(tmp_path, name="test-bench")
    assert cfg_path.is_file()
    assert (tmp_path / "data" / "evaluation").is_dir()
    assert (tmp_path / "reports").is_dir()

    loaded = load_workspace_config(cfg_path)
    assert loaded.name == "test-bench"
    assert loaded.budget.total_usd == Decimal("5.00")
    assert loaded.budget.per_run_usd == Decimal("1.00")
    assert loaded.budget.per_case_usd == Decimal("0.05")
    assert loaded.budget.require_priced is False

    # Fails if exists without force
    with pytest.raises(FileExistsError):
        init_workspace(tmp_path, name="test-bench", force=False)

    # Overwrites when force=True
    reinit = init_workspace(tmp_path, name="forced-bench", force=True)
    assert reinit.is_file()


def test_cli_init_command(tmp_path: Path):
    """CLI runport init creates workspace config."""
    res = runner.invoke(app, ["init", "--dir", str(tmp_path), "--name", "cli-bench"])
    assert res.exit_code == 0
    assert "Runport Workspace Initialized Successfully" in res.stdout
    assert (tmp_path / "runport.yaml").is_file()


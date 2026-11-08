"""Unit tests for Milestone 5 - Task 5.4: Multi-Tenant Architecture & RBAC.

Specifications: docs/MULTI_USER_SECURITY_MODEL.md section 5:
1. Two organizations, two projects each: strict cross-project isolation.
2. RBAC permissions matrix: Viewer, Member, Approver, Admin.
3. Self-approval prevention on billable plans:
   - A member cannot approve.
   - An approver cannot approve their own billable plan when allow_self_approval is False.
   - An approver CAN approve another user's billable plan.
   - An approver CAN approve their own plan if allow_self_approval is explicitly True.
4. API key project scoping: keys from Project A cannot access Project B.
5. Append-only audit logging with zero secret leakage.
"""

from datetime import datetime, timezone, timedelta
import json
from pathlib import Path
import pytest

from runport.core.config import settings
from runport.core.tenancy import (
    Permission,
    Role,
    TenantContext,
    TenantManager,
    has_permission,
)
from runport.storage.db import DatabaseManager


@pytest.fixture
def test_db(tmp_path: Path, monkeypatch):
    """Sets up an isolated database for multi-tenancy testing."""
    db_file = tmp_path / "multi_tenant.db"
    monkeypatch.setattr(type(settings), "db_path", property(lambda self: db_file))
    db = DatabaseManager(db_file)
    db.init_db()
    return db


def test_schema_migration_creates_default_tenant(test_db):
    """Verifies Migration 6 sets up default organization and project for local mode."""
    default_org = test_db.get_organization("default-org")
    assert default_org is not None
    assert default_org["name"] == "Default Organization"

    default_proj = test_db.get_project("default")
    assert default_proj is not None
    assert default_proj["org_id"] == "default-org"


def test_multi_tenant_isolation(test_db):
    """Acceptance Test 1: Two organizations, two projects each have complete isolation."""
    tm = TenantManager(db=test_db)

    # Org 1: Alpha Corp
    org1 = tm.create_organization("Alpha Corp", org_id="org-alpha")
    proj1a = tm.create_project("Alpha Fraud Detection", org_id="org-alpha", project_id="p-alpha-fraud")
    proj1b = tm.create_project("Alpha Recommendation", org_id="org-alpha", project_id="p-alpha-recs")

    # Org 2: Beta Industries
    org2 = tm.create_organization("Beta Industries", org_id="org-beta")
    proj2a = tm.create_project("Beta Logistics", org_id="org-beta", project_id="p-beta-logistics")
    proj2b = tm.create_project("Beta Customer Support", org_id="org-beta", project_id="p-beta-support")

    # Verify project listing scoped by organization
    alpha_projects = tm.db.list_projects(org_id="org-alpha")
    assert len(alpha_projects) == 2
    assert {p["project_id"] for p in alpha_projects} == {"p-alpha-fraud", "p-alpha-recs"}

    beta_projects = tm.db.list_projects(org_id="org-beta")
    assert len(beta_projects) == 2
    assert {p["project_id"] for p in beta_projects} == {"p-beta-logistics", "p-beta-support"}

    # Scoped API keys
    tm.db.create_api_key(
        key_id="k-alpha-1",
        key_hash="hash-alpha-1",
        name="Alpha CI Key",
        scopes=["runs:read", "runs:execute"],
        project_id="p-alpha-fraud",
    )
    tm.db.create_api_key(
        key_id="k-beta-1",
        key_hash="hash-beta-1",
        name="Beta CI Key",
        scopes=["runs:read", "runs:execute"],
        project_id="p-beta-logistics",
    )

    # Project Alpha cannot see Beta keys
    alpha_keys = tm.db.list_api_keys(project_id="p-alpha-fraud")
    assert len(alpha_keys) == 1
    assert alpha_keys[0]["key_id"] == "k-alpha-1"

    beta_keys = tm.db.list_api_keys(project_id="p-beta-logistics")
    assert len(beta_keys) == 1
    assert beta_keys[0]["key_id"] == "k-beta-1"


def test_rbac_permission_matrix():
    """Acceptance Test 2a: Strict RBAC matrix matching docs/MULTI_USER_SECURITY_MODEL.md."""
    # VIEWER
    assert has_permission(Role.VIEWER, Permission.TARGETS_READ)
    assert has_permission(Role.VIEWER, Permission.RUNS_READ)
    assert has_permission(Role.VIEWER, Permission.BUDGET_READ)
    assert not has_permission(Role.VIEWER, Permission.PLANS_CREATE)
    assert not has_permission(Role.VIEWER, Permission.RUNS_EXECUTE)
    assert not has_permission(Role.VIEWER, Permission.PLANS_APPROVE)
    assert not has_permission(Role.VIEWER, Permission.SECRETS_WRITE)

    # MEMBER
    assert has_permission(Role.MEMBER, Permission.TARGETS_READ)
    assert has_permission(Role.MEMBER, Permission.DATASETS_WRITE)
    assert has_permission(Role.MEMBER, Permission.PLANS_CREATE)
    assert has_permission(Role.MEMBER, Permission.RUNS_EXECUTE)
    assert not has_permission(Role.MEMBER, Permission.PLANS_APPROVE)
    assert not has_permission(Role.MEMBER, Permission.BUDGET_RECONCILE)

    # APPROVER
    assert has_permission(Role.APPROVER, Permission.RUNS_EXECUTE)
    assert has_permission(Role.APPROVER, Permission.PLANS_APPROVE)
    assert not has_permission(Role.APPROVER, Permission.BUDGET_POLICY)
    assert not has_permission(Role.APPROVER, Permission.MEMBERS_WRITE)

    # ADMIN
    assert has_permission(Role.ADMIN, Permission.PLANS_APPROVE)
    assert has_permission(Role.ADMIN, Permission.BUDGET_RECONCILE)
    assert has_permission(Role.ADMIN, Permission.BUDGET_POLICY)
    assert has_permission(Role.ADMIN, Permission.SECRETS_WRITE)
    assert has_permission(Role.ADMIN, Permission.MEMBERS_WRITE)


def test_self_approval_prevention_on_billable_plans(test_db):
    """Acceptance Test 2b: A principal cannot approve a plan it requested when self-approval is off."""
    tm = TenantManager(db=test_db)
    tm.create_organization("Acme Corp", org_id="org-acme")

    # Project 1: Default (allow_self_approval=False)
    tm.create_project("Strict Project", org_id="org-acme", project_id="p-strict", allow_self_approval=False)
    tm.add_member(user_id="dev-alice", project_id="p-strict", role=Role.MEMBER)
    tm.add_member(user_id="lead-bob", project_id="p-strict", role=Role.APPROVER)

    ctx_alice = tm.get_context("dev-alice", "p-strict")
    assert ctx_alice is not None

    ctx_bob = tm.get_context("lead-bob", "p-strict")
    assert ctx_bob is not None

    # Case 1: Member Alice tries to approve
    can_approve, reason = ctx_alice.can_approve_plan(requester="dev-alice", is_billable=True)
    assert not can_approve
    assert "does not have permission 'plans:approve'" in reason

    # Case 2: Approver Bob approves Alice's billable plan -> ALLOWED
    can_approve, reason = ctx_bob.can_approve_plan(requester="dev-alice", is_billable=True)
    assert can_approve
    assert reason == "Approval authorized."

    # Case 3: Approver Bob tries to approve his OWN billable plan -> BLOCKED
    can_approve, reason = ctx_bob.can_approve_plan(requester="lead-bob", is_billable=True)
    assert not can_approve
    assert "Self-approval is forbidden on billable plans" in reason

    # Case 4: Approver Bob approves his own UNBILLED/LOCAL plan -> ALLOWED
    can_approve, reason = ctx_bob.can_approve_plan(requester="lead-bob", is_billable=False)
    assert can_approve

    # Project 2: Explicitly allows self approval (e.g. solo dev project)
    tm.create_project("Solo Project", org_id="org-acme", project_id="p-solo", allow_self_approval=True)
    tm.add_member(user_id="lead-bob", project_id="p-solo", role=Role.APPROVER)

    ctx_bob_solo = tm.get_context("lead-bob", "p-solo")
    assert ctx_bob_solo is not None
    can_approve, reason = ctx_bob_solo.can_approve_plan(requester="lead-bob", is_billable=True)
    assert can_approve


def test_append_only_audit_log_with_secret_scrubbing(test_db):
    """Acceptance Test 5: Audit log is durable and scrubs all credentials."""
    tm = TenantManager(db=test_db)
    tm.create_organization("Security Corp", org_id="org-sec")
    tm.create_project("Audit Project", org_id="org-sec", project_id="p-sec")

    # Record audit events
    aid1 = tm.log_audit(
        project_id="p-sec",
        principal="admin@sec.com",
        action="api_key:created",
        resource_type="api_key",
        resource_id="k-sec-1",
        details={
            "key_name": "Prod Ingestion Key",
            "api_key": "sk-secret-token-abcdef1234567890",  # Sensitive key
            "token": "Bearer sensitive-auth-token-9988",    # Sensitive token
        },
    )

    aid2 = tm.log_audit(
        project_id="p-sec",
        principal="lead@sec.com",
        action="plan:approved",
        resource_type="plan",
        resource_id="plan-8899",
        details={"plan_fingerprint": "a" * 64, "approved_spend_usd": "0.50"},
    )

    logs = tm.get_audit_trail("p-sec")
    assert len(logs) == 2

    log1 = [l for l in logs if l["audit_id"] == aid1][0]
    assert log1["principal"] == "admin@sec.com"
    assert log1["action"] == "api_key:created"

    # Invariant 7: Zero secret leakage
    details_str = json.dumps(log1["details"])
    assert "[REDACTED" in details_str
    assert "sk-secret" not in details_str
    assert "sensitive-auth" not in details_str


def test_api_key_last_used_tracking(test_db):
    """Acceptance Test 4: API key verification updates last_used_at."""
    test_db.create_api_key(
        key_id="k-tracked-01",
        key_hash="hash-tracked-01",
        name="Usage Tracking Key",
        scopes=["runs:read"],
        project_id="default",
    )

    key_before = test_db.get_api_key_by_hash("hash-tracked-01")
    assert key_before is not None
    assert key_before["key_id"] == "k-tracked-01"

    # Querying updates last_used_at
    key_after = test_db.get_api_key_by_hash("hash-tracked-01")
    assert key_after["last_used_at"] is not None

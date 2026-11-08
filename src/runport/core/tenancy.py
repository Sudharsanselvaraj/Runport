"""Multi-Tenant Architecture and Role-Based Access Control (RBAC).

Milestone 5 - Task 5.4: Multi-Tenant Architecture per docs/MULTI_USER_SECURITY_MODEL.md.
Specification:
1. Hierarchy: Organization -> Project -> Membership(user, project, role).
2. Roles:
   - VIEWER: read-only access (targets, datasets, runs, budget, traces).
   - MEMBER: standard developer (datasets write, plans create, runs execute).
   - APPROVER: spend authorizer (member permissions + plans:approve).
   - ADMIN: project administrator (approver permissions + budget:reconcile, budget:policy, secrets:write, members:write).
3. Invariant: Self-approval is strictly forbidden on billable plans unless the project explicitly allows it.
4. Project-scoped data layer: cross-project queries are strictly isolated.
5. Append-only audit logging: records principal, action, time, project, resource, never logging secrets.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
import json
from typing import Any, Dict, List, Optional, Set, Tuple
import uuid

from runport.providers.base import scrub_secrets
from runport.storage.db import DatabaseManager


class Role(str, Enum):
    """Canonical RBAC roles within a Runport project."""

    VIEWER = "viewer"
    MEMBER = "member"
    APPROVER = "approver"
    ADMIN = "admin"


class Permission(str, Enum):
    """Granular permissions governed by Runport security model."""

    TARGETS_READ = "targets:read"
    DATASETS_READ = "datasets:read"
    RUNS_READ = "runs:read"
    BUDGET_READ = "budget:read"
    TRACES_READ = "traces:read"

    DATASETS_WRITE = "datasets:write"
    PLANS_CREATE = "plans:create"
    RUNS_EXECUTE = "runs:execute"
    TRACES_WRITE = "traces:write"

    PLANS_APPROVE = "plans:approve"

    BUDGET_RECONCILE = "budget:reconcile"
    BUDGET_POLICY = "budget:policy"
    SECRETS_WRITE = "secrets:write"
    MEMBERS_WRITE = "members:write"


# Permission matrix strictly matching docs/MULTI_USER_SECURITY_MODEL.md section 2.2
ROLE_PERMISSIONS: Dict[Role, Set[str]] = {
    Role.VIEWER: {
        Permission.TARGETS_READ.value,
        Permission.DATASETS_READ.value,
        Permission.RUNS_READ.value,
        Permission.BUDGET_READ.value,
        Permission.TRACES_READ.value,
    },
    Role.MEMBER: {
        # All Viewer permissions
        Permission.TARGETS_READ.value,
        Permission.DATASETS_READ.value,
        Permission.RUNS_READ.value,
        Permission.BUDGET_READ.value,
        Permission.TRACES_READ.value,
        # Member permissions
        Permission.DATASETS_WRITE.value,
        Permission.PLANS_CREATE.value,
        Permission.RUNS_EXECUTE.value,
        Permission.TRACES_WRITE.value,
    },
    Role.APPROVER: {
        # All Member permissions
        Permission.TARGETS_READ.value,
        Permission.DATASETS_READ.value,
        Permission.RUNS_READ.value,
        Permission.BUDGET_READ.value,
        Permission.TRACES_READ.value,
        Permission.DATASETS_WRITE.value,
        Permission.PLANS_CREATE.value,
        Permission.RUNS_EXECUTE.value,
        Permission.TRACES_WRITE.value,
        # Approver permission
        Permission.PLANS_APPROVE.value,
    },
    Role.ADMIN: {
        # All Approver permissions
        Permission.TARGETS_READ.value,
        Permission.DATASETS_READ.value,
        Permission.RUNS_READ.value,
        Permission.BUDGET_READ.value,
        Permission.TRACES_READ.value,
        Permission.DATASETS_WRITE.value,
        Permission.PLANS_CREATE.value,
        Permission.RUNS_EXECUTE.value,
        Permission.TRACES_WRITE.value,
        Permission.PLANS_APPROVE.value,
        # Admin permissions
        Permission.BUDGET_RECONCILE.value,
        Permission.BUDGET_POLICY.value,
        Permission.SECRETS_WRITE.value,
        Permission.MEMBERS_WRITE.value,
    },
}


def has_permission(role: str | Role, permission: str | Permission) -> bool:
    """Checks whether a given role holds the specified permission."""
    if isinstance(role, Role):
        r = role
    else:
        try:
            r = Role(str(role).lower())
        except ValueError:
            return False
    perm_val = permission.value if isinstance(permission, Permission) else str(permission)
    return perm_val in ROLE_PERMISSIONS.get(r, set())


@dataclass
class TenantContext:
    """Scoped execution context binding a principal to a specific project and organization."""

    project_id: str
    org_id: str
    principal: str
    role: Role
    allow_self_approval: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)

    def has_permission(self, permission: str | Permission) -> bool:
        """Evaluates whether the caller holds the requested permission in this project."""
        return has_permission(self.role, permission)

    def can_approve_plan(self, requester: str, is_billable: bool) -> Tuple[bool, str]:
        """Enforces plan approval authorization rules.

        Rules:
        1. Caller must have plans:approve permission (Role.APPROVER or Role.ADMIN).
        2. A principal cannot approve a plan it requested unless allow_self_approval is True.
        """
        if not self.has_permission(Permission.PLANS_APPROVE):
            return False, f"Role '{self.role.value}' does not have permission 'plans:approve'."

        if requester == self.principal and is_billable and not self.allow_self_approval:
            return False, "Self-approval is forbidden on billable plans when allow_self_approval is disabled."

        return True, "Approval authorized."


class TenantManager:
    """Manages multi-tenant organizations, projects, memberships, and security policies."""

    def __init__(self, db: Optional[DatabaseManager] = None) -> None:
        self.db = db or DatabaseManager()
        self.db.init_db()

    def create_organization(self, name: str, org_id: Optional[str] = None) -> Dict[str, Any]:
        """Creates a top-level tenant organization."""
        oid = org_id or f"org-{uuid.uuid4().hex[:8]}"
        return self.db.create_organization(oid, name)

    def create_project(
        self,
        name: str,
        org_id: str,
        project_id: Optional[str] = None,
        allow_self_approval: bool = False,
        settings: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Creates an isolated workspace project under an organization."""
        pid = project_id or f"proj-{uuid.uuid4().hex[:8]}"
        cfg = dict(settings or {})
        cfg["allow_self_approval"] = allow_self_approval
        return self.db.create_project(pid, org_id, name, cfg)

    def add_member(
        self,
        user_id: str,
        project_id: str,
        role: str | Role,
    ) -> Dict[str, Any]:
        """Adds or updates a user membership in a project."""
        r = role if isinstance(role, Role) else Role(str(role).lower())
        mid = f"mem-{uuid.uuid4().hex[:8]}"
        return self.db.add_membership(mid, user_id, project_id, r.value)

    def get_context(self, user_id: str, project_id: str) -> Optional[TenantContext]:
        """Resolves tenant authorization context for a user in a project."""
        mem = self.db.get_membership(user_id, project_id)
        if not mem:
            return None

        proj = self.db.get_project(project_id)
        if not proj:
            return None

        settings = proj.get("settings", {})
        allow_self_approval = bool(settings.get("allow_self_approval", False))

        return TenantContext(
            project_id=project_id,
            org_id=proj["org_id"],
            principal=user_id,
            role=Role(mem["role"]),
            allow_self_approval=allow_self_approval,
            metadata=settings,
        )

    def log_audit(
        self,
        project_id: str,
        principal: str,
        action: str,
        resource_type: Optional[str] = None,
        resource_id: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Appends an event to the project's audit log with automatic secret scrubbing."""
        aid = f"aud-{uuid.uuid4().hex[:12]}"
        self.db.record_audit_event(
            audit_id=aid,
            project_id=project_id,
            principal=principal,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            details=details,
        )
        return aid

    def get_audit_trail(self, project_id: str, limit: int = 100) -> List[Dict[str, Any]]:
        """Retrieves audit trail for a project."""
        return self.db.list_audit_logs(project_id, limit=limit)

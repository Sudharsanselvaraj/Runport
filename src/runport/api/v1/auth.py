"""Scoped API key authentication and authorization for Runport REST API v1.

Specification: docs/SDK_API_CONTRACT.md section 2.1.
Enforces:
- Scoped permissions: targets:read, datasets:read, datasets:write, plans:create, plans:approve, runs:execute, runs:read, traces:write, budget:read, budget:reconcile.
- Constant-time secret comparison.
- Support for Bearer rp_<key_id>_<secret> or master RUNPORT_API_TOKEN.
"""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import hmac
import os
from typing import Any, Callable, Dict, List, Optional
from fastapi import Depends, Request

from runport.api.v1.errors import ForbiddenError, UnauthorizedError
from runport.core.config import settings
from runport.storage.db import DatabaseManager

# Standard Runport v1 scopes
SCOPE_TARGETS_READ = "targets:read"
SCOPE_DATASETS_READ = "datasets:read"
SCOPE_DATASETS_WRITE = "datasets:write"
SCOPE_PLANS_CREATE = "plans:create"
SCOPE_PLANS_APPROVE = "plans:approve"
SCOPE_RUNS_EXECUTE = "runs:execute"
SCOPE_RUNS_READ = "runs:read"
SCOPE_TRACES_WRITE = "traces:write"
SCOPE_BUDGET_READ = "budget:read"
SCOPE_BUDGET_RECONCILE = "budget:reconcile"

ALL_SCOPES = frozenset(
    {
        SCOPE_TARGETS_READ,
        SCOPE_DATASETS_READ,
        SCOPE_DATASETS_WRITE,
        SCOPE_PLANS_CREATE,
        SCOPE_PLANS_APPROVE,
        SCOPE_RUNS_EXECUTE,
        SCOPE_RUNS_READ,
        SCOPE_TRACES_WRITE,
        SCOPE_BUDGET_READ,
        SCOPE_BUDGET_RECONCILE,
    }
)

_LOOPBACK_HOSTS = frozenset({"127.0.0.1", "localhost", "::1", "testclient"})


def hash_api_key(key: str) -> str:
    """Computes SHA-256 hash of API key for secure database lookup."""
    return hashlib.sha256(key.strip().encode("utf-8")).hexdigest()


def extract_token(request: Request) -> Optional[str]:
    """Extracts bearer token from Authorization header or X-Runport-Token."""
    auth_header = request.headers.get("Authorization", "").strip()
    if auth_header.startswith("Bearer "):
        token = auth_header[7:].strip()
        if token:
            return token

    x_token = request.headers.get("X-Runport-Token", "").strip()
    if x_token:
        return x_token

    return None


def require_scope(required_scope: str) -> Callable[[Request], Dict[str, Any]]:
    """FastAPI dependency factory enforcing API key authentication and scoped access."""

    async def _dependency(request: Request) -> Dict[str, Any]:
        token = extract_token(request)
        master_token = os.environ.get("RUNPORT_API_TOKEN")

        # 1. Master environment token grants all scopes
        if token and master_token:
            if hmac.compare_digest(token.encode("utf-8"), master_token.encode("utf-8")):
                return {
                    "key_id": "master",
                    "name": "Master Environment Token",
                    "scopes": list(ALL_SCOPES),
                    "is_master": True,
                }

        # 2. Database-backed API key lookup
        db = DatabaseManager(settings.db_path)
        db.init_db()

        if token:
            key_hash = hash_api_key(token)
            key_record = db.get_api_key_by_hash(key_hash)

            if key_record:
                # Check expiration
                if key_record.get("expires_at"):
                    try:
                        exp = datetime.fromisoformat(key_record["expires_at"])
                        if exp.tzinfo is None:
                            exp = exp.replace(tzinfo=timezone.utc)
                        if datetime.now(timezone.utc) > exp:
                            raise UnauthorizedError("API key has expired.")
                    except ValueError:
                        pass

                granted_scopes = set(key_record.get("scopes", []))
                if "*" in granted_scopes or required_scope in granted_scopes:
                    return key_record

                raise ForbiddenError(
                    f"API key lacks required scope: '{required_scope}'.",
                    details={"granted_scopes": list(granted_scopes), "required_scope": required_scope},
                )

            # Token was provided but matched neither master token nor database key
            raise UnauthorizedError("Invalid or revoked API key.")

        # 3. No token provided: Check for local loopback development bypass
        client_host = request.client.host if request.client else ""
        if not master_token and client_host in _LOOPBACK_HOSTS:
            # Check if user has explicitly created any API keys
            existing_keys = db.list_api_keys()
            if not existing_keys:
                # Permissive loopback dev mode when no auth is configured
                return {
                    "key_id": "loopback-dev",
                    "name": "Local Loopback Operator",
                    "scopes": list(ALL_SCOPES),
                    "is_master": True,
                }

        raise UnauthorizedError("Valid API credentials required via Bearer token.")

    return _dependency

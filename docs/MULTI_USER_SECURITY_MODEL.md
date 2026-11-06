# Multi-User Security Model

**Status:** Runport is single-tenant today. This document records the current model precisely and designs the one required before
any shared deployment. Multi-user hosting must not be announced until every acceptance test in section 5 passes.

---

## 1. Current model (evidence)

| Concern | Today | File |
|:---|:---|:---|
| Network access | No token: loopback clients with a loopback `Host` only. Token: every `/api` request must send the one shared token. | `api/app.py` `_access_policy_middleware` |
| Identity | None. The approver name in the Web UI is free text. | `api/routes/runs.py` `approve_ui_run` |
| Tenancy | One workspace = one directory and one SQLite file; `core/config.settings` is process-global. | `core/config.py`, `core/workspace.py` |
| Approvals | Persisted, expiring, single use, human channels only. Any API caller can use the `web_ui` channel. | `services/approvals.py` |
| Secrets | Server environment, referenced from `runport.yaml` as `$NAME`. Shared by all callers. | `connectors/registry.py` |
| Execution | Synchronous inside the API request; no worker isolation. | `api/routes/runs.py` |
| Audit | Ledger and approval records are durable; API access is not logged. | `storage/db.py`, `plan_approvals` |
| Dashboard | Cannot send a token, so token mode is API/CLI only. | `web/src/App.tsx` |

**Supported deployment today:** one person, one machine, loopback. Anything else is unsupported.

---

## 2. Target model

### 2.1 Entities

`Organization` → `Project` (owns targets, datasets, runs, ledger, budget policy, secrets) → `Membership(user, project, role)`.
`ApiKey(principal, project, scopes, expires_at, last_used_at)`; only a hash of the secret is stored.

### 2.2 Roles and permissions

| Permission | Viewer | Member | Approver | Admin |
|:---|:---:|:---:|:---:|:---:|
| `targets:read`, `datasets:read`, `runs:read`, `budget:read` | ✓ | ✓ | ✓ | ✓ |
| `datasets:write`, `plans:create`, `runs:execute` (approved plans only) | | ✓ | ✓ | ✓ |
| `plans:approve` | | | ✓ | ✓ |
| `budget:reconcile`, `budget:policy`, `secrets:write`, `members:write` | | | | ✓ |

Rules:
- A principal cannot approve a plan it requested unless the project explicitly allows self-approval (default: off for billable plans).
- Agent and CI keys are created without `plans:approve`; granting it is an audited admin action.
- Every query is scoped by `project_id` in the data layer, not only in route handlers (tests attempt cross-project access by id).

### 2.3 Secrets

Per-project secrets encrypted at rest (envelope encryption with a server key from the environment or a KMS). Target specs keep
`$NAME` references resolved against the project's secrets, never the server's environment. Secret values are write-only through
the API and never returned.

### 2.4 Persistence and execution

- Postgres for hosted mode (SQLite stays for local mode) behind the same repository layer, with a real migration tool.
- Budget reservations in a transaction with row locks (`docs/UNIVERSAL_EXECUTION_ARCHITECTURE.md`, F0), so concurrent runs cannot jointly exceed a cap.
- Runs as jobs on workers; per-project concurrency limits; cancellation; worker processes do not share `settings` state across projects.

### 2.5 Network and transport

TLS termination in front of the app; session cookies (`HttpOnly`, `Secure`, `SameSite=Lax`) plus CSRF tokens for the dashboard;
bearer keys for API, SDK and MCP over HTTP. Rate limits per key.

### 2.6 Audit log

Append-only table: who, what (login, key created, plan created/approved/executed, budget reconciled, policy changed, secret changed,
export downloaded), project, time, request id. Exportable; never contains secret values.

---

## 3. Threats and controls

| Threat | Control |
|:---|:---|
| Agent approves its own spend | No `plans:approve` on agent keys; self-approval off; approval UI requires a session, not a key |
| Cross-project data access | Project-scoped repository layer; tests per resource |
| Secret exfiltration via targets (e.g. SSRF to a capture server) | Existing `validate_safe_url`; per-project egress allowlist option; secrets only injected into the target they are configured for |
| Concurrent overspend | Atomic reservations (F0) |
| Replay of approvals | `ApprovalStore.consume` single use (exists) |
| Stolen API key | Hashing, expiry, scopes, last-used tracking, revocation, audit |
| Oversized or malicious trace ingestion | Size limits, schema validation, redaction before storage |

---

## 4. Prerequisites (must land first)

F0 integrity fixes; F1 trace schema (so traces are project-scoped from the start); F2 jobs and REST v1; F3 API keys.

---

## 5. Acceptance tests for hosted mode

1. Two organizations, two projects each: no endpoint, SDK call or MCP tool returns another project's targets, datasets, runs, traces, ledger or secrets.
2. A member cannot approve; an approver cannot approve their own billable plan when self-approval is off.
3. Ten concurrent runs against a $1.00 cap never book more than $1.00 plus the documented in-flight tolerance.
4. Revoked keys fail immediately; expired keys fail; every key use is in the audit log.
5. Secrets are never present in API responses, logs, traces or exports (scan test).
6. Backup and restore drill documented and tested.

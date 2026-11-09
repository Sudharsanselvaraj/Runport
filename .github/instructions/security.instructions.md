---
applyTo: "src/runport/api/**,src/runport/mcp_server/**,src/runport/core/budget*.py,src/runport/storage/**"
---
# Security & Multi-Tenant Isolation Instructions

Apply these rules when reviewing or authoring code in authentication, MCP, budget, or storage modules:

1. **Strict Tenant Isolation**:
   - Every request is bound to an authenticated credential with a `project_id`.
   - Operations must filter queries by `project_id`. A tenant must never read, modify, or execute plans, runs, or ledger entries belonging to another tenant.
   - Master/admin escalation (`is_master=True`) must only be granted through explicit master credentials.

2. **MCP Authorization & Scopes**:
   - The MCP HTTP server must authenticate the API key and forward the credential context.
   - Plan execution (`execute_approved_benchmark`) must verify the authenticated project owns the plan.
   - MCP tool calls must strictly enforce required scopes before execution:
     - `runs:read`: `list_runs`, `get_run`, `get_results`
     - `runs:execute`: `execute_approved_benchmark`, `cancel_job`
     - `plans:create`: `create_plan`
     - `budget:read`: `get_budget_status`
     - `budget:reconcile`: `reconcile_budget`

3. **Financial & Spend Integrity**:
   - Ledger reservations and spend bookings must be partitioned strictly by `project_id`.
   - Provenance vocabulary is restricted to: `ACTUAL`, `ESTIMATED`, `UNRESOLVED`, `UNAVAILABLE`.
   - Unresolved spend blocks subsequent runs fail-closed.
   - Reconciliations must only reconcile entries within the authenticated project.

4. **Secret Scrubbing & Leakage Prevention**:
   - API keys, authorization headers, and provider secrets must be redacted before persisting to disk, logging, or exporting in traces.

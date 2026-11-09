# Runport — GitHub Copilot Custom Instructions

You are assisting on **Runport**, a universal, local-first open-source LLM, prompt, and workflow benchmarking platform.
Review and write code adhering strictly to the architecture invariants, tenant isolation boundaries, and fail-closed security rules defined below.

---

## 1. Architectural Invariants (Never Weaken)

1. **Null is not 0**: Missing tokens, latency, confidence, or cost remain `None` / `UNAVAILABLE`. Never fabricate or default missing telemetry to zero.
2. **Fixed Provenance Vocabulary**: All cost accounting strictly uses:
   - `ACTUAL`: Exact provider-reported USD spend.
   - `ESTIMATED`: Verified catalog rate × reported tokens.
   - `UNRESOLVED`: Billed request with unknown cost.
   - `UNAVAILABLE`: Zero-cost unpriced / local execution.
3. **Strict Runner Guard Order**:
   `Authorization Check` → `Privacy Gate` → `Preflight Budget & Context Check` → `Transport Execution` → `Strict Validation` → `Persistence` → `Spend Booking` (booked as `UNRESOLVED` if cost is unavailable).
4. **Unresolved Spend Blocks Execution**: Unresolved ledger entries block further live runs fail-closed until reconciled via `runport budget reconcile`.
5. **Cryptographic Plan Fingerprint**: Execution plan fingerprint SHA-256 binds candidate models, endpoint routes, dataset hash, prompt template hash, and budget caps. Mismatched or stale approvals are rejected.
6. **Immutable Sources**: Source datasets are hashed (SHA-256) before and after evaluation to guarantee immutability.
7. **Zero Leakage & Secret Scrubbing**: API keys, bearer tokens, and secrets are automatically scrubbed from request logs, trace events, and exports.
8. **Agreement is Not Correctness**: Model-to-model consensus is never presented as accuracy. Supervised metrics require human ground-truth approval.
9. **No Tuning on Held-Out Splits**: Decision thresholds and hyper-parameters are calibrated on DEV only, frozen, and evaluated unchanged on TEST.
10. **Zero Simulation in Core Modules**: Test doubles exist only under `tests/`. Replay executions are isolated, carry provenance `REPLAYED`, and book `$0.00` spend.

---

## 2. Review Priorities

### P0 — Critical Security & Authorization
- **Tenant Isolation**: Every database query, plan retrieval, run lookup, and budget query must filter strictly by `project_id`. Cross-project data access is strictly forbidden unless the credential explicitly possesses `is_master=True`.
- **MCP Authorization & Scopes**:
  - The MCP server must receive and validate the authenticated credential.
  - Plan executions must verify ownership (`_plan_or_error`).
  - Tools must enforce granted API key scopes (`runs:read`, `runs:execute`, `plans:create`, `budget:read`, `budget:reconcile`).
- **Financial & Budget Integrity**:
  - Ledger reservations must be isolated per project.
  - Budget reconciliation must only operate within the authenticated project.
  - Never allow negative reservations or unreserved spend leakage.

### P1 — Execution Reliability & Concurrency
- **Worker Heartbeat & Crash Recovery**:
  - Background execution workers must maintain an active heartbeat (`heartbeat_at`).
  - Stale worker detection must safely clean up dead processes and release orphaned budget reservations without clobbering active workers.
- **Database Migrations**:
  - Schema modifications in SQLite must be idempotent and safe under concurrent thread access.

### P1 — API & SDK Parity
- **TypeScript SDK (`packages/sdk-ts`)**:
  - Must remain in strict contract parity with the FastAPI REST API and Python SDK (`src/runport_sdk`).
  - Must run cleanly on Node 22+ using native `--experimental-strip-types`.
- **Python SDK (`src/runport_sdk`)**:
  - Must support authentication headers, tenant headers, and proper error propagation.

---

## 3. Technology Stack & Coding Standards
- **Python**: 3.11+, Pydantic v2 (`model_dump`, `model_validate`), FastAPI, Typer, SQLite WAL mode.
- **TypeScript**: Node 22+, native type stripping, strict null checks.
- **Testing**: All automated tests run offline with blocked sockets and mock transports.

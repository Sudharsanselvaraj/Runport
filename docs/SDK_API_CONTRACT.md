# SDK and API Contract

Two layers: the **in-process Python SDK** that exists today, and a **versioned REST v1 contract** (design) that a remote Python
client and the TypeScript SDK will wrap. Both sit on `ExecutionService`; neither has its own execution logic.

---

## 1. Existing: in-process Python SDK (`src/runport/sdk.py`)

| Function | Behaviour (verified by `tests/test_sdk.py`) |
|:---|:---|
| `plan(target, dataset, *, target_id=None, sample_size=None, service=None) -> SdkPlan` | `target` is a `runport.yaml` target id or catalog model id, a `Target`, or a plain callable (wrapped in `PythonCallableTarget`). `dataset` is a JSONL path or a list of dicts. Stores a `PENDING` plan; sends nothing. |
| `approve_interactively(plan)` | Typed `RUN LIVE … PLAN <fingerprint>` in a terminal; refused without a TTY. Channel `cli_interactive`. |
| `approve_with_ci_token(plan, token)` | Requires `approver.token_approver_enabled: true`; `token` must equal the fingerprint. Channel `ci_token`. |
| `execute(plan, *, score=True) -> ExecutionOutcome` | Runs once through `GenericRunner`; a second call is refused. |
| `benchmark(target, dataset, …)` | Plan + approve + execute. All-local plans use the `local_only` channel; anything else asks for the typed phrase. |

**Not stable yet:** return types are internal (`ExecutionOutcome`, `GenericRunResult`, `TargetResult`). v0.2 must introduce
public result models (section 3) and keep the internal types private.

---

## 2. Design: REST v1

Base path `/api/v1`. JSON only. All responses typed (Pydantic models exported to OpenAPI; the TypeScript SDK is generated from that schema).
Current unversioned `/api/*` routes stay for the bundled dashboard until it moves to v1, then are removed in a minor release with notice.

### 2.1 Auth

`Authorization: Bearer rp_<key_id>_<secret>`. Keys belong to a principal and a project and carry scopes:
`targets:read`, `datasets:read`, `datasets:write`, `plans:create`, `plans:approve`, `runs:execute`, `runs:read`, `traces:write`
(ingestion), `budget:read`, `budget:reconcile`. Agents' and CI keys never get `plans:approve` unless an operator grants it on purpose.
Until multi-user hosting exists (`docs/MULTI_USER_SECURITY_MODEL.md`), the single `RUNPORT_API_TOKEN` maps to all scopes.

### 2.2 Resources

| Method and path | Purpose | Scope |
|:---|:---|:---|
| `GET /targets`, `GET /targets/{id}` | Workspace targets and catalog models; type, billing, header names only | `targets:read` |
| `GET /datasets`, `POST /datasets` | List, upload (validated, hashed) | `datasets:*` |
| `POST /plans` | Body: `target_ids`, `dataset` (name or inline cases), `sample_size`. Returns `Plan` (`PENDING`, fingerprint, worst-case spend, blockers, expires_at) | `plans:create` |
| `GET /plans/{plan_id}` | Plan status | `runs:read` |
| `POST /plans/{plan_id}/approve` | Body: `fingerprint`. Human channel | `plans:approve` |
| `POST /plans/{plan_id}/runs` | Submit an approved plan. Returns `202` with `Run` (`queued`) | `runs:execute` |
| `GET /runs/{run_id}` | Status: `queued`, `running`, `completed`, `halted`, `failed`, `cancelled` | `runs:read` |
| `POST /runs/{run_id}/cancel` | Stops after the current case | `runs:execute` |
| `GET /runs/{run_id}/results?cursor=` | Per-case results with typed scores | `runs:read` |
| `GET /runs/{run_id}/traces/{case_id}` | Canonical trace | `runs:read` |
| `GET /runs/{run_id}/events` | Server-sent events: case start/finish, halts | `runs:read` |
| `POST /traces` (OTLP/JSON or Runport `Trace`) | Ingestion | `traces:write` |
| `GET /budget` | Ceilings, spend by provenance, unresolved entries | `budget:read` |

### 2.3 Models (abridged)

```text
Plan     { plan_id, fingerprint, status, expires_at, target_ids[], case_count, projected_max_cost_usd|null,
           per_target[{target_id, type, billing, priced, projected_cost_usd|null}], blockers[], requested_by, approved_by|null }
Run      { run_id, plan_id, target_id, status, total_cases, successful, failed, skipped,
           booked_spend_usd, unresolved_cases, mean_latency_ms|null, halted_reason|null, created_at, finished_at|null }
Result   { case_id, status, output_text|null, latency_ms|null, tokens_in|null, tokens_out|null,
           cost_usd|null, cost_basis, scores[{name, kind, value|null, evaluator}], error_code|null }
```

Rules: unmeasured numbers are `null`; costs are strings (decimal); `cost_basis` uses the fixed vocabulary.

### 2.4 Errors

`{ "error": { "code": "...", "message": "...", "details": {...} } }` with stable codes:
`approval_required` (428), `approval_invalid` (403), `plan_blocked` (409), `budget_exceeded` (402), `unresolved_spend` (409),
`confidentiality_violation` (400), `invalid_target_spec` (400), `not_found` (404), `unauthorized` (401), `forbidden` (403).

### 2.5 Idempotency and versioning

`POST /plans/{id}/runs` accepts `Idempotency-Key`; a plan executes at most once regardless (`ApprovalStore.consume`).
Breaking changes go to `/api/v2`. The SDKs follow semantic versioning and declare the API version they target.

---

## 3. Remote clients (design)

**Python** (`runport.client.Client`): wraps REST v1 with the same verbs as the in-process SDK (`plan`, `approve`, `execute`,
`get_run`, `results`, `trace`), plus `wait(run_id)`. Uses `httpx` (already a dev dependency; would become a `client` extra).

**TypeScript** (`@runport/sdk`): generated types from OpenAPI plus a small hand-written client; `fetch`-based; no approval helper
that can approve without an explicit call by the caller.

**Instrumentation (later):** `runport.instrument` context managers / decorators that emit canonical spans (or OTel spans with
GenAI attributes) for code that is not run by Runport's executor.

---

## 4. Acceptance criteria for v0.2

- OpenAPI schema for v1 generated in CI and diffed against the committed one.
- Contract tests run the same scenarios against the in-process SDK, the Python client and the TypeScript client (against a test server).
- No SDK path can approve a billable plan without `plans:approve` or a human channel (tests per client).

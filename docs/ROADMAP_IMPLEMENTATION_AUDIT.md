# Roadmap Implementation Audit

**Audited tree:** branch `claude/charming-wiles-d0e566` at `d99d167`, which contains `main` up to `1179841` (merged in `09d6c54`).
**Date:** 2026-11-06.
**Scope:** the nine capabilities missing from the v0.1.0 announcement, plus the foundations they depend on.

This document separates **evidence** (what the code does, with file paths) from **recommendations** (what to build). Every
"verified" statement below was checked against the code or by running a command on this tree. It replaces an earlier version
of this file written against `main` alone, which predated the shared execution service, the MCP server and the Python SDK and
contained factual errors (section 7).

---

## 1. Verified baseline

Commands run on `d99d167` (macOS, Python 3.12, uv):

| Check | Result |
|:---|:---|
| `uv run pytest -q` | **456 passed** |
| `uv run pytest -q examples/plugins` | 26 passed, 5 skipped |
| `uv run ruff check .` | All checks passed |
| `uv run mypy` | No issues (56 files: `core`, `runs`, `connectors`, `scorers`, `workloads`, `services`, `traces`, `sdk.py`, `mcp_server`, and the migrated runners) |
| `npm test` (web) | 18 passed |
| `git tag`, `git ls-remote --tags origin` | No tags. **v0.1.0 is described in `CHANGELOG.md` and `pyproject.toml` but has not been tagged**, so `.github/workflows/release.yml` (PyPI publish on `v*` tags) has never run for it. |

mypy does **not** cover `api/`, `cli/`, `tui/`, `observability/`, `evaluation/replay_scoring.py` or `classification/threshold.py`;
the latter two have about 20 known type errors.

---

## 2. Capability classification

| # | Capability | Status | One-line reason |
|:---|:---|:---|:---|
| 1 | MCP client and server ecosystem | **PARTIALLY IMPLEMENTED** | Client (tools, stdio + Streamable HTTP) and server (stdio, 11 tools, resources, prompts) exist and are tested with the official MCP SDK; no server HTTP transport, no resources/prompts in the client, no MCP auth. |
| 2 | Public Python SDK | **PARTIALLY IMPLEMENTED** | `runport.sdk` works in-process with the shared guards; there is no remote client, no stable versioned contract and no published package. |
| 3 | Public TypeScript SDK | **NOT IMPLEMENTED** | No package. The REST API it would wrap is unversioned and synchronous. |
| 4 | Native LangGraph per-step tracing | **NOT IMPLEMENTED** | `connectors/langgraph.py` is a one-shot HTTP POST to `/runs/wait`. |
| 5 | Universal agent trajectory evaluation | **BLOCKED BY ARCHITECTURE** | There is no span/trajectory field on `TargetResult` and no trace table. |
| 6 | OpenTelemetry ingestion | **NOT IMPLEMENTED** | No OTLP endpoint, no OTel/OpenInference parsing, no dependency. |
| 7 | Langfuse export | **NOT IMPLEMENTED** | Only a Langfuse-*shaped* JSON/CSV importer exists. |
| 8 | Production multi-user hosting | **BLOCKED BY ARCHITECTURE** | One shared token, no users or tenants, SQLite file per workspace, synchronous runs inside HTTP requests. |
| 9 | Universal framework instrumentation | **NOT IMPLEMENTED** | No instrumentation API; frameworks are reached only as black-box HTTP or Python callables. |

### 2.1 MCP ecosystem: PARTIALLY IMPLEMENTED

**Evidence**
- Client: `src/runport/connectors/mcp.py`, `McpToolTarget`, `McpSession`, `StdioTransport`, `StreamableHttpTransport`,
  `validate_json_schema`. Implements `initialize` with version negotiation (`2025-06-18`, `2025-03-26`, `2024-11-05`), paginated
  `tools/list`, `tools/call`, cancellation on timeout, session teardown, secret redaction (header values and credential-named env vars).
  Cost is never $0 for a billable HTTP server: billing mode is `local` for stdio, `billable` for non-loopback URLs.
- Server: `src/runport/mcp_server/server.py`, `RunportMcpServer`; CLI `runport mcp serve` (`cli/commands/plans.py`). Tools:
  `list_connectors`, `list_models`, `list_targets`, `list_datasets`, `validate_target`, `create_benchmark_plan`,
  `request_benchmark_approval`, `get_plan_status`, `execute_approved_benchmark`, `get_run`, `get_evaluation_results`, `compare_runs`.
  Resources `runport://{connectors,models,targets,datasets,runs,budget}` and template `runport://runs/{run_id}`. Prompts
  `benchmark_target`, `investigate_failed_cases`, `compare_candidates`.
- Execution goes through `ExecutionService.execute_by_ids` → `GenericRunner`. No approve tool exists; `ApprovalStore.approve`
  rejects any channel outside `cli_interactive`, `web_ui`, `ci_token`, `local_only` (`services/approvals.py`).
- Tests: `tests/test_mcp_connector.py` (16, offline fixture server `tests/fixtures/mcp_fixture_server.py`), `tests/test_mcp_server.py`
  (2 end-to-end flows over real stdio: the official `mcp` 2.3.0 `ClientSession` and Runport's own client).

**Missing**
- Server over Streamable HTTP (needed for remote agents), and its authentication.
- Client support for `resources/*`, `prompts/*`, sampling, OAuth discovery; MCP sessions are not recorded as trace spans.
- Protocol `2025-11-25` / `2026-07-28` (the SDK's newest) are not spoken; the server answers `2025-06-18`, which the SDK accepts.
- Per-tool authorization: anyone who can start the stdio server can call every tool (acceptable for a local process, not for HTTP).

**Completion criteria:** Streamable HTTP server with token or OAuth auth and per-tool scopes; MCP calls emitted as spans; client
resources/prompts; protocol-version matrix test against the official SDK.

### 2.2 Public Python SDK: PARTIALLY IMPLEMENTED

**Evidence:** `src/runport/sdk.py` (`plan`, `approve_interactively`, `approve_with_ci_token`, `execute`, `benchmark`), re-exported
lazily from `runport/__init__.py`. All calls use `ExecutionService`. A plain function can be benchmarked unchanged; local-only
plans auto-approve via the `local_only` channel, verified in `ApprovalStore.approve`. Tests: `tests/test_sdk.py` (4).

**Missing:** a remote client for a shared Runport server, typed public result models (it returns internal `ExecutionOutcome` /
`GenericRunResult` dataclasses), datasets/runs/traces read APIs, async support, semantic-versioning guarantees, docs reference.
**Risk:** the return types are internal and will change when traces are added (section 2.5).

### 2.3 TypeScript SDK: NOT IMPLEMENTED

**Evidence:** none in `web/` or elsewhere; `web/` is the dashboard. The REST API (`src/runport/api/routes/`) is unversioned
(`/api/...`), returns untyped `Dict[str, Any]` from most routes, and runs live benchmarks synchronously inside `POST /api/runs`.
**Depends on:** versioned REST contract (`docs/SDK_API_CONTRACT.md`), async run jobs, API keys.

### 2.4 Native LangGraph per-step tracing: NOT IMPLEMENTED

**Evidence:** `src/runport/connectors/langgraph.py` subclasses `HttpWorkflowConnector`, posts to `/runs/wait`, reads
`messages.-1.content`. The capability registry (`connectors/registry.py`, `CONNECTOR_MATRIX`) correctly lists per-step trace as "no".
**Depends on:** canonical trace schema and storage (2.5), streaming transport.

### 2.5 Universal agent trajectory evaluation: BLOCKED BY ARCHITECTURE

**Evidence:**
- `TargetResult` (`targets/base.py`) has `metadata: Dict` only. Dify node data lands in `metadata["per_node_data"]`; MCP tool
  details in `metadata`; RAG retrieval in `metadata["retrieval"]`. Nothing is typed or persisted as spans.
- Storage (`storage/db.py`) has `evaluation_runs`, `evaluation_results`, `budget_ledger`, `model_portfolio`, `plan_approvals`,
  `schema_migrations`. No trace or span table.
- `traces/models.py` (`TraceRecord`, `ObservationSpan`) is an import model for diagnosis, not linked to runs.
- Scorers (`scorers/`, `evaluation/evaluator.py`) score a single output string.

**Blocker:** a canonical trace schema and persistence (`docs/CANONICAL_TRACE_SCHEMA.md`) must exist before any trajectory scorer.

### 2.6 OpenTelemetry ingestion: NOT IMPLEMENTED

**Evidence:** no `opentelemetry`/`otlp`/`openinference` reference in `src/`, `tests/` or `pyproject.toml`. **Depends on:** trace schema,
an ingestion endpoint with auth, size limits and redaction.

### 2.7 Langfuse export: NOT IMPLEMENTED

**Evidence:** `traces/importer.py` reads Langfuse-style JSON/CSV (`latency` in seconds, `usage`, `observations`).
`observability/export.py` exports Runport's own sanitized JSONL/CSV/ZIP bundle, not the Langfuse ingestion API format.
**Depends on:** trace schema; then a mapper to the Langfuse public ingestion API.

### 2.8 Production multi-user hosting: BLOCKED BY ARCHITECTURE

**Evidence:**
- Auth (`api/app.py`, `_access_policy_middleware`): no token → loopback only with Host check; token set → one shared token for all
  callers. No users, roles, organizations or projects.
- Any API caller can approve plans (`POST /api/runs/approve`, channel `web_ui`); the approver name is free text.
- Workspace = one directory with one SQLite file; settings are process-global (`core/config.py`, `settings`).
- Live runs execute synchronously inside the request (`api/routes/runs.py`); no job queue, cancellation or worker isolation.
- Secrets come from the server's environment for every caller.
**Blocker:** identity, tenancy and a job model are prerequisites, not features (`docs/MULTI_USER_SECURITY_MODEL.md`).

### 2.9 Universal framework instrumentation: NOT IMPLEMENTED

**Evidence:** integration paths today are black-box: `http_workflow`, `python` callable (`connectors/python_target.py`), `subprocess`,
`mcp` tools. The registry lists LangChain, CrewAI and LlamaIndex as `planned`. No decorator, context manager or callback handler
emits steps. **Depends on:** trace schema, an instrumentation API in the SDK, and OTel ingestion (so instrumentation can be OTel-native).

---

## 3. Architecture audit

| Question | Answer | Evidence |
|:---|:---|:---|
| One shared execution service? | **Yes, for live target runs.** | `services/execution.py` `ExecutionService` → `runs/executor.py` `GenericRunner`, used by CLI `benchmark`/`benchmark-rag`, `/api/plan`, `/api/runs`, `/api/targets/test`, `runport.sdk`, the MCP server. `BenchmarkRunner.run`, `RAGBenchmarkRunner.run` and `ClassificationRunner.run_batch` also execute via `GenericRunner` (with their own plan objects and a `TokenApprover` built from a `LiveAuthorization`). The only `provider.generate(` left is in `connectors/openrouter.py`. |
| One canonical run and trace schema? | **No.** | Runs: `evaluation_runs`/`evaluation_results`. Classification: `PredictionRecord` JSONL (`classification/records.py`). Events: `RequestEvent` JSONL (`observability/events.py`). Imported traces: `TraceRecord`. Four shapes, none linked. |
| One connector contract? | **Yes.** | `Target.execute → TargetResult`; `connectors/registry.py` `build_target` and `CONNECTOR_MATRIX`. |
| One evaluation interface? | **No.** | `scorers/base.py`, `evaluation/evaluator.py` `RubricEvaluator`, `rag/evaluator.py`, `classification/metrics.py`, `GenericRunner(case_scorer=…)`. Score provenance (`EvaluationScore.evaluator_type`) is **not persisted**: `evaluation_results` stores a heuristic word-overlap score in the `accuracy` column. |
| One authentication/authorization model? | **Partly.** | API: shared token or loopback. Approvals: `ApprovalStore` channels. No per-user identity anywhere. |
| One budget/approval path? | **Yes, with two gaps.** | `GenericRunner` guard order and `ApprovalStore`. Gaps in section 4 (per-run cap, concurrency). The library runners accept a `LiveAuthorization` object directly; it is a capability object, not a persisted approval. |
| Durable persistence? | **Single-node only.** | SQLite WAL; `PRAGMA`-based migrations in `DatabaseManager.init_db`; no migration framework, no Postgres. |
| Stable public API? | **No.** | `/api/*` unversioned; responses mostly untyped dicts; SDK returns internal dataclasses. |

**Duplicate or divergent paths still present**
1. `api/routes/runs.py` replay branch builds its own run record; CLI replay uses `runs/replay.py` + `evaluation/replay_scoring.py`. Both are offline, but they persist differently.
2. `ClassificationRunner` writes `PredictionRecord`s to its own store in addition to `evaluation_results`.
3. The dashboard's live telemetry stream (`/api/events`, `observability/monitor.py`) reads `request_events.jsonl`, but **no code in `src/` writes `RequestEvent`s**, so it stays empty for every run.

---

## 4. Security and data-integrity audit

| Area | Status | Evidence / gap |
|:---|:---|:---|
| Remote API auth | Fixed on this branch | Fails closed without a token; constant-time compare; DNS-rebinding Host check (`api/app.py`). Dashboard cannot send a token, so token mode is API/CLI-only. |
| API token handling | Single static secret | No rotation, scopes or per-client identity. |
| Secret storage | Environment only | `runport.yaml` must use `$NAME`/`${NAME}` (`registry.check_spec_has_no_literal_secrets`, `workspace._check_no_secrets`). No vault, no per-user secrets. |
| User/org isolation | None | Single tenant. |
| Approval generation/consumption | Fixed on this branch | Persisted, expiring, fingerprint-bound, atomic single use (`services/approvals.py`; concurrency test in `tests/test_integrity_security.py`). Any API caller can approve via `web_ui`. |
| Budget enforcement | **Two gaps** | (a) The per-run ceiling is checked against each case's worst case, never against the run's accumulated spend (`GenericRunner.execute_plan`, Guard 3; `BudgetService.check_spend_permitted`). Lifetime and pilot caps are cumulative and hold. (b) Preflight and booking are separate statements: two concurrent runs can both pass preflight and overspend together. |
| Unknown cost | Fixed on this branch | Billable + no cost → `UNRESOLVED`, run halts (`runs/executor.py` Guard 7; `targets/base.py` `BillingMode`). |
| Null vs zero | Mostly fixed | Traces, RAG correctness, plan projections. **Remaining:** the Compare page draws 50 ms / 90 ms when latency is missing (`web/src/App.tsx`, `mean_latency_ms || 50`). |
| Trace redaction | Present | `scrub_secrets` on results, exports, MCP output; PII redaction in `datasets/redaction.py`. |
| Concurrent execution | Unsafe for spend | See budget gap (b). SQLite serializes writes but not the check-then-book sequence. |
| Transaction boundaries | Per statement | Each ledger write is its own transaction; a run is not atomic. |
| Background jobs | None | Live API runs block the request; no cancel, no resume. |
| Audit logging | Partial | The ledger and `plan_approvals` (who approved, when, which fingerprint) are durable; API access is not logged. |

---

## 5. Dependency graph

```mermaid
flowchart TD
    F0[F0 Integrity fixes: per-run cap, atomic reservation, event emission, score provenance] --> F1
    F1[F1 Canonical trace schema + span storage] --> T1[Trajectory on TargetResult]
    F2[F2 Versioned REST v1 + async run jobs] --> SDKPY[Remote Python client]
    F2 --> SDKTS[TypeScript SDK]
    F3[F3 Identity: API keys with scopes] --> F2
    T1 --> LG[LangGraph per-step tracing]
    T1 --> TRAJ[Trajectory evaluation]
    T1 --> OTEL[OTel / OpenInference ingestion]
    T1 --> LFX[Langfuse export]
    OTEL --> INSTR[Universal instrumentation]
    SDKPY --> INSTR
    F3 --> MCPHTTP[MCP over HTTP with auth]
    F3 --> MU[Multi-user hosting: tenants, RBAC, Postgres, workers]
    F2 --> MU
```

Order of work: **F0 → F1 → F3 → F2**, then the features. F0 and F1 are small relative to what they unblock.

---

## 6. Executive summary

**Reusable now:** the `Target` contract and registry; `ExecutionService` + `GenericRunner` as the single live path; persisted
approvals; billing modes and `UNRESOLVED` handling; the MCP client and server; the in-process SDK; scrubbing and SSRF checks;
the capability matrix and its drift test.

**Build first (foundations):**
1. F0 integrity fixes: cumulative per-run cap, atomic budget reservation, `RequestEvent` emission from `GenericRunner`, persisted score provenance.
2. F1 canonical trace schema and span tables, with `TargetResult.trajectory`.
3. F3 scoped API keys (prerequisite for any remote SDK, MCP over HTTP, or hosting).
4. F2 versioned REST v1 with asynchronous run jobs.

**Needs refactoring:** settings are process-global (`core/config.settings`), which blocks multi-tenant serving; runs execute
inside HTTP requests; four unlinked run/trace shapes.

**Could block v1.0:** multi-user hosting (identity, tenancy, Postgres, workers) is the largest and riskiest item; it should be its
own release with security tests. OpenTelemetry ingestion widens the attack surface (untrusted payload size, PII) and needs limits
and redaction from day one.

---

## 7. Corrections to the previous version of this audit

The earlier file on `main` (`1179841`) stated, among others:
- "CLI commands invoke `GenericRunner`" — at that commit the CLI live path used `BenchmarkRunner` with its own loop.
- MCP and Python SDK "NOT IMPLEMENTED" — true for `main`, not for this branch.
- `src/runport/targets/python.py` / `PythonTarget` — no such file or class; the target is `PythonCallableTarget` in `connectors/python_target.py`.
- `docs/safety.md` (same commit) cited a `runport benchmark --live --approve <fingerprint>` flag (does not exist) and "DNS pinning"
  (the code resolves and checks before connecting; the HTTP client resolves again). Both are corrected in `docs/safety.md`.

---

## 8. Test results on the audited tree

See section 1. All commands were run on `d99d167`; nothing here is inferred from CI.

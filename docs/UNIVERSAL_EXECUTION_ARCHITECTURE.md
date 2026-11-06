# Universal Execution Architecture

How every Runport interface executes work, what exists today, and the changes needed so the SDKs, MCP over HTTP, framework
instrumentation and multi-user hosting can be built on one path. "Current" sections describe code on
`claude/charming-wiles-d0e566` at `d99d167`; "Target" sections are design.

---

## 1. Rule

**Every live request to a target goes through `ExecutionService` and `GenericRunner`.** No interface implements its own transport
loop, budget check, approval or spend booking. Replay never touches the network or the live ledger.

---

## 2. Current architecture

```text
 CLI benchmark / benchmark-rag / approve     Web API /api/plan /api/runs /api/targets/test     runport.sdk     runport mcp serve
                 \                                         |                                      |               /
                  +----------------------------- services/execution.py: ExecutionService ---------------------+
                                     plan()  ──► services/approvals.py: ApprovalStore (SQLite plan_approvals)
                                     approve() (human channels only)
                                     execute() ──► runs/executor.py: GenericRunner.execute_plan
                                                       1 authorization (approver + unresolved-spend block)
                                                       2 privacy gate (forbidden fields, confidentiality for non-local targets)
                                                       3 preflight budget per case
                                                       4 transport: Target.execute (connectors/*)
                                                       5 strict validation
                                                       6 persistence (evaluation_runs / evaluation_results) + case_scorer
                                                       7 spend booking (ACTUAL / ESTIMATED / UNAVAILABLE / UNRESOLVED + halt)
```

Library runners keep their public APIs and execute through `GenericRunner` with a plan they build themselves and a
`TokenApprover` derived from a caller-supplied `LiveAuthorization`:
`evaluation/runner.py` `BenchmarkRunner.run`, `rag/runner.py` `RAGBenchmarkRunner.run` (and `run_planned`, which uses
`ExecutionService`), `classification/runner.py` `ClassificationRunner.run_batch`.

### 2.1 Key types

| Type | File | Role |
|:---|:---|:---|
| `Target`, `TargetResult`, `BillingMode`, `CostBasis` | `targets/base.py` | Connector contract, result, billing mode, provenance |
| `build_target`, `CONNECTOR_MATRIX` | `connectors/registry.py` | Declarative specs (`$ENV` secrets), capability matrix |
| `ExecutionPlan` | `runs/planner.py` | SHA-256 fingerprint over targets, dataset hash, prompt hash, cap |
| `ExecutionService`, `PlanSummary` | `services/execution.py` | Plan / approve / execute; worst-case projection; blockers |
| `ApprovalStore` | `services/approvals.py` | `PENDING → APPROVED → CONSUMED`, expiry, channels |
| `GenericRunner`, `GenericRunResult` | `runs/executor.py` | Guarded execution, halting on unresolved spend |
| `BudgetService` | `core/budget.py` | Ceilings, ledger, reconciliation |

### 2.2 Known gaps in the current path

1. **Per-run ceiling is not cumulative at runtime.** Guard 3 compares one case's worst case with the per-run ceiling; it never adds the run's spend so far.
2. **Check-then-book race.** Preflight and booking are separate; concurrent runs can overspend together.
3. **No events.** `GenericRunner` writes no `RequestEvent` (`observability/events.py`), so the live telemetry stream is empty.
4. **No spans.** Step-level data lives in untyped `TargetResult.metadata`.
5. **Score provenance dropped.** `case_scorer` output is persisted to columns named `accuracy`/`groundedness` without the evaluator type.
6. **Synchronous API runs.** `POST /api/runs` executes inside the request.
7. **Process-global settings.** `core/config.settings` (paths, policy) is shared by every request.

---

## 3. Target architecture

```text
 Interfaces: CLI · TUI · Web UI · REST v1 · Python SDK (in-process + remote) · TypeScript SDK · MCP (stdio + HTTP)
                                          │
                     Auth context (principal, project, scopes)        ← new (F3)
                                          │
                               ExecutionService (per project)
                     plan · approve · submit · cancel · get · list
                                          │
                 Job queue (SQLite table now, Postgres later)          ← new (F2)
                                          │
                                   Worker: GenericRunner
      guards 1–7, plus: budget reservation (atomic) · RequestEvent emission · span recording   ← new (F0, F1)
                                          │
                 Persistent store: runs · results · spans · scores(provenance) · ledger · approvals · audit
                                          │
                 Evaluation engine: output scorers · span scorers · trajectory scorers
                                          │
                 Exporters / ingesters: Runport bundle · OTel/OpenInference in · Langfuse out
```

### 3.1 Changes, in order

**F0 Integrity (no new features)**
- *Budget reservation.* Before each case, `BudgetService.reserve(run_id, worst_case)` inserts a `RESERVED` ledger row inside one
  `BEGIN IMMEDIATE` transaction that also re-checks run, pilot and total ceilings including other open reservations. Booking
  converts the reservation to the actual entry; an aborted run releases it. This closes gaps 1 and 2.
- *Events.* `GenericRunner` emits `RequestEvent` start/finish per case through an injectable sink (`observability/events.py`).
- *Score provenance.* `case_scorer` returns typed scores (`kind: ground_truth | judge | heuristic`); persisted with the score.

**F1 Trace schema** (`docs/CANONICAL_TRACE_SCHEMA.md`): `TargetResult.trajectory: Optional[Trace]`; span table; connectors that
see steps (Dify workflows, MCP, RAG retrieval) fill it.

**F2 Jobs and REST v1** (`docs/SDK_API_CONTRACT.md`): `submit()` returns a run id immediately; a worker executes; clients poll or
stream events. Cancel sets a flag the runner checks between cases.

**F3 Identity**: an `AuthContext` passed into `ExecutionService`; approval channels become permissions (`plans:approve`).

### 3.2 Interface responsibilities

| Interface | Does | Never does |
|:---|:---|:---|
| CLI / TUI | Parse args, show plans, collect the typed phrase, call `approve` with `cli_interactive` | Build targets outside `resolve`, call connectors |
| Web UI / REST | Validate input, map errors to HTTP codes, approve with `web_ui` for an authorized user | Execute inside the request (after F2) |
| SDK | Build targets from user code, call the service | Approve billable plans without a person or CI token |
| MCP | Plan, request approval, execute approved plans, read results | Approve, define new targets, read secrets |

### 3.3 Invariant tests to keep

`tests/test_integrity_security.py`, `tests/test_cli_execution.py`, `tests/test_sdk.py`, `tests/test_mcp_server.py`,
`tests/test_web_api.py`, `tests/test_core_invariants.py`. New ones for F0: concurrent runs cannot exceed a cap together; a run's
spend cannot exceed the per-run ceiling even when actual costs beat the estimate; every executed case produces start and finish events.

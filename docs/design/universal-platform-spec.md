# Universal Benchmarking Platform: Implementation Audit and Architecture Spec

Status: **Draft for review**. Audited tree: `main` at `2291c21`, plus the MCP connector commits on `claude/charming-wiles-d0e566` (`461af37`, `9e132f0`).

Goal: a developer can benchmark an existing model, agent, workflow or application from the CLI, Web UI, SDK/REST API or MCP without rebuilding it around Runport. Every entry point calls the same planning, guard and execution services.

Everything under "Proposed" is design, not shipped behaviour. Everything under "Verified" was checked against the code at the revision above.

---

## 0. Implementation status (2026-11-05, branch `claude/charming-wiles-d0e566`)

Sections 1 to 9 below are the original audit and design; this section records what has since been built. Where they disagree, this section is current.

| Item | Status | Where |
|---|---|---|
| F1 targets unreachable from interfaces | **Done.** CLI (`benchmark --target`), Web API (`/api/plan`, `/api/runs`), SDK and MCP server all run through `ExecutionService` → `GenericRunner` | `services/execution.py`, `cli/commands/benchmarks.py`, `api/routes/`, `sdk.py`, `mcp_server/` |
| F2 `/api/targets/test` bypass | **Done** (plan → approve → execute) | `api/routes/targets.py` |
| F3 trace zeros | **Done** | `traces/models.py`, `traces/importer.py`, `traces/analyzer.py` |
| F4 overclaimed capabilities | **Done**; claims are now generated from one registry and checked by tests | `connectors/registry.py`, `tests/test_capability_registry.py` |
| F5 stale limits in ARCHITECTURE.md | **Done** | `docs/ARCHITECTURE.md` |
| F6 four status tables | **Done** (all embed the generated matrix) | `README.md`, `docs/connectors*.md`, `web/src/data/connectors.ts` |
| F7 trajectory schema | Not started (M2) | — |
| Unknown spend booked as $0 | **Done**: billing modes; billable + no cost → `UNRESOLVED`, run halts | `targets/base.py`, `runs/executor.py` |
| Remote API without token | **Done**: fails closed; DNS-rebinding Host check | `api/app.py` |
| Approval lifecycle | **Done**: persisted, expiring, fingerprint-bound, atomic single use, human channels only | `services/approvals.py` |
| `/api/runs` live returned "queued" without running | **Done**: executes | `api/routes/runs.py` |
| MCP server (4.2) | **Done** (stdio, hand-written JSON-RPC; tested with the official SDK client) | `mcp_server/server.py`, `tests/test_mcp_server.py` |
| Workspace `targets:` (5.1) | **Done** using the existing `TargetConfig` list, `$NAME`/`${NAME}` secrets | `core/workspace.py`, `connectors/registry.py` |
| RAG and classification runners on GenericRunner | **Not done**: they keep their own guarded loops (live authorization, preflight, confidentiality gate, unresolved booking) | `rag/runner.py`, `classification/runner.py` |
| `runport smoke-test --live` | Approves but sends nothing (unchanged); not an execution path | `cli/commands/benchmarks.py` |
| TypeScript SDK, OTel ingestion, framework adapters, JUnit, CI action | Not started (M4–M6) | — |

---

## 1. Audit: what exists today

### 1.1 Verified module map

| Capability | Where it lives | State |
|---|---|---|
| Target contract | `src/runport/targets/base.py` (`Target`, `TargetResult`, `CostBasis`, `TargetType`) | Solid. One `execute()` per case. No trajectory or span field. |
| Connectors | `src/runport/connectors/*.py` | 10 connectors plus `mcp.py` (new). Flowise, Langflow, n8n and LangGraph are thin `HttpWorkflowConnector` subclasses. |
| Guarded generic executor | `src/runport/runs/executor.py` (`GenericRunner`), `runs/planner.py` (`ExecutionPlan`, SHA-256 fingerprint) | Implements the 7-stage guard order over any `Target`. **Only tests call it.** |
| Live benchmark path used by CLI/API | `evaluation/runner.py` (`BenchmarkRunner`), `rag/runner.py`, `classification/runner.py`, `providers/openrouter.py` | OpenRouter-only for live runs. |
| Replay | `runs/replay.py`, `evaluation/replay_scoring.py` | Works from CLI (`benchmark --replay`) and API (`POST /api/runs` with `is_replay`). |
| Budget and approval | `core/budget.py`, `core/budget_policy.py`, `core/live_guard.py`, `core/approvers.py`, `core/workspace.py` | Fail-closed ledger, typed-phrase live authorization bound to the plan fingerprint. |
| Scorers | `scorers/` (match, classification, extraction, generation, llm_judge, performance, stats) | Output-level only. No tool, trajectory or span scorers. |
| Traces | `traces/models.py`, `traces/importer.py`, `traces/analyzer.py` | Langfuse-shaped JSON/CSV import plus failure diagnosis. No OpenTelemetry or OpenInference. |
| Observability/export | `observability/` (events, export, bundle_verify, budget_audit) | Sanitized trace export (zip), event tail. |
| Plugins | `core/plugins.py` (entry-point groups for targets and scorers), `examples/plugins/` | Works. This is the natural extension seam. |
| CLI | `cli/main.py`, `cli/commands/*.py` | `init`, `benchmark`, `benchmark-rag`, `compare-runs`, `validate-dataset`, `annotate`, `export-traces`, `import-traces`, `api-preflight`, `ui`, `web`, `budget {status,reconcile,audit,policy,purge-simulated,raise-pilot-ceiling}`, `models {list,roster}` |
| REST API | `api/routes/*.py` | `budget`, `datasets`, `events`, `models`, `plan`, `runs` (list/get/approve/create), `reports`, `setup`, `targets` (list, `POST /test`) |
| SDK | `src/runport/__init__.py` | Exports only `__version__`. There is no `benchmark()` entry point. No TypeScript SDK. |
| MCP | `connectors/mcp.py` (client, tools only) | New on the branch above. No Runport MCP server. |
| CI | `.github/workflows/ci.yml` | ruff, format, mypy, pytest, plugin tests. No benchmark-as-CI action, no JUnit output. |

### 1.2 Corrections to the strategy document

| Claim in the strategy | What the code shows |
|---|---|
| "No MCP implementation" | Was true on `main`. The branch now has an MCP **client** for tools (stdio and Streamable HTTP, schema validation, offline tests). Resources, prompts and the MCP **server** are still missing. |
| "`require_priced: true` was the approved policy" | Code (`core/workspace.py:17`, the `init` template at `core/workspace.py:311`) and `docs/DECISIONS.md:26` all say `false`. **Decision needed** (see section 9). Nothing in the repo records a `true` approval. |
| Custom integrations are "supported" | Supported as `Target` classes, but no CLI command or API route runs them through the guarded runner (finding F1). |
| "Langfuse import/export references" | Import exists (`traces/importer.py`). There is no Langfuse **export** code. Export is Runport's own sanitized bundle. |

### 1.3 Findings to fix before adding features

| # | Finding | Evidence | Severity |
|---|---|---|---|
| F1 | Connector targets (HTTP, Python, Dify, Ollama, MCP…) cannot be benchmarked from any interface. `GenericRunner` implements the guard order, but no CLI command or API route calls it. "Bring your project" does not work end to end today. | `grep GenericRunner` hits only `runs/executor.py` and three test files | **Blocker** for the product goal |
| F2 | `POST /api/targets/test` calls `connector.execute()` directly. It skips live authorization, budget preflight and spend booking. With `openai_compat` and an `api_key` this is a billed request that never reaches the ledger. That breaks AGENTS.md invariants 3 and 4. **Fixed in `a79b3d4`:** the route now returns a plan (HTTP 428) and runs only through `GenericRunner` with a matching single-use approval. | `api/routes/targets.py` | ~~High~~ Fixed |
| F3 | Trace model defaults missing telemetry to zero (`latency_ms=0.0`, `total_tokens=0`, `prompt_tokens=0`, `completion_tokens=0`, span `latency_ms=0.0`). That breaks invariant 1 (null is not 0). | `traces/models.py:26,41-44` | **High** |
| F4 | Advertised capabilities with no code behind them. LangGraph lists `streaming` and `per_step_trace` but only POSTs `/runs/wait` and reads `messages.-1.content`. Flowise and Langflow list `streaming` but have no streaming path. | `connectors/langgraph.py`, `flowise.py`, `langflow.py` vs `docs/connectors/README.md` and `README.md:201` | Medium (trust) |
| F5 | Stale spend limits: `$18 / $2 / $0.50 / $0.02`. | `docs/ARCHITECTURE.md:60` vs `core/workspace.py:11-14` (`$5 / $1 / $0.05`, pilot `$1`) | Medium |
| F6 | Connector status lives in four places. Only two are cross-checked by a test. `ollama` is documented as `ACTUAL-LOCAL`, which is not in the fixed provenance vocabulary. The code uses `UNAVAILABLE` (`connectors/ollama.py:120`). "`UNAVAILABLE` ($0.00 compute)" wording contradicts null-is-not-0. | `README.md:189-201`, `docs/connectors.md`, `docs/connectors/README.md`, `web/src/data/connectors.ts`, `tests/test_landing_connectors.py` | Medium |
| F7 | No shared trace or trajectory schema. `TargetResult.metadata` is free-form, so tool calls, handoffs and spans cannot be scored uniformly. | `targets/base.py`, `traces/models.py` | Medium (blocks agent evaluation) |

---

## 2. Architecture

One core and five entry points. Entry points only parse input and render output. They never decide whether a run may happen.

```
CLI / TUI   Web UI   REST API   Python SDK   MCP server   (TS SDK → REST)
     \         |         |          |            |
      └────────┴─────────┴──────────┴────────────┘
                         │
              runport.services  (new, thin facade)
   ProjectService · DatasetService · ExperimentService · RunService · ReportService
                         │
   ExecutionPlan (fingerprint) → Guard pipeline → GenericRunner → ResultStore
   Authorization · Privacy · Budget preflight · Transport · Validation · Persistence · Spend booking
                         │
      Target adapters (connectors/, plugins)      Trace normalizer (traces/)
```

### 2.1 Component map

| Component (strategy name) | Existing module to extend | New module | Notes |
|---|---|---|---|
| `TargetAdapter` | `targets/base.py` `Target` | none | Keep the name `Target`. Add an optional `trajectory` field to `TargetResult` (section 3). |
| `ExperimentEngine` | `runs/planner.py`, `runs/executor.py` | `services/experiments.py`, `services/runs.py` | Make `GenericRunner` the **only** executor for live `Target` runs. `BenchmarkRunner` becomes an OpenRouter `Target` over time (M2). |
| `BudgetService` | `core/budget.py`, `core/live_guard.py`, `core/approvers.py` | none | Generalize `LiveAuthorization.covers(model_id)` to cover target ids. |
| `DatasetProvider` | `dataset/manager.py`, `dataset/leakage.py`, `classification/splits.py` | none | Already versioned by hash. |
| `Evaluator` | `scorers/`, `evaluation/evaluator.py`, `rag/evaluator.py` | `scorers/tools.py`, `scorers/trajectory.py` | Scorers get a `scope`: `output`, `span`, `trajectory`, `session`. |
| `TraceNormalizer` | `traces/importer.py` | `traces/schema.py`, `traces/otel.py`, `traces/openinference.py` | Section 3. |
| `MCPClientManager` | `connectors/mcp.py` | `mcp/client_manager.py` (when several servers per target are needed) | Section 4.1. |
| `ResultStore` | `storage/db.py` | migration for `spans` table | Same SQLite WAL file. |
| `ReportEngine` | `reports/generator.py`, `observability/export.py` | `reports/junit.py` | Add JUnit XML for CI. |
| Capability registry | the four tables in F6 | `src/runport/connectors/registry.py` | Section 6. |
| Project registration | `core/workspace.py` (`runport.yaml`) | `targets:` section in the workspace file | Section 5. |

### 2.2 Non-negotiables carried into every new interface

- No interface may call `Target.execute()` for a live, potentially billed request outside `GenericRunner`. F2 is the counter-example to remove.
- A live run needs a `LiveAuthorization` that matches the plan fingerprint. MCP, SDK and API callers can **request** a plan and receive its fingerprint and phrase. Only an approver (interactive CLI, Web UI approve button, or a configured token approver) can grant it. A tool call never approves its own plan.
- Missing telemetry stays `None`. Cost provenance uses only `ACTUAL`, `ESTIMATED`, `UNRESOLVED`, `UNAVAILABLE`, plus `REPLAYED` for replays.

---

## 3. Normalized trace and trajectory schema (proposed, `traces/schema.py`)

Aligned with OpenTelemetry GenAI semantic conventions so OTel and OpenInference spans map in without loss. Pydantic v2, every telemetry field `Optional` with `None` meaning "not reported".

| Model | Fields |
|---|---|
| `Trace` | `trace_id`, `run_id?`, `case_id?`, `session_id?`, `source` (`runport`, `otel`, `openinference`, `langfuse`, `mcp`), `source_ref?`, `started_at?`, `ended_at?`, `spans[]`, `outcome?` |
| `Span` | `span_id`, `parent_id?`, `kind` (`agent`, `llm`, `tool`, `retrieval`, `rerank`, `handoff`, `workflow_step`, `other`), `name`, `started_at?`, `ended_at?`, `latency_ms?`, `status` (`ok`, `error`, `timeout`, `unset`), `error?`, `attributes{}` |
| `LlmAttrs` | `provider?`, `model?`, `tokens_in?`, `tokens_out?`, `cost_usd?`, `cost_basis` |
| `ToolAttrs` | `tool_name`, `arguments` (scrubbed), `result` (scrubbed, size-capped), `schema_valid?`, `server?` (e.g. MCP server id) |
| `HandoffAttrs` | `from_agent`, `to_agent`, `reason?` |
| `RetrievalAttrs` | `query?`, `doc_ids[]`, `scores[]?`, `k?` |

Rules:
- `TargetResult` gets `trajectory: Optional[Trace] = None`. Connectors that can see internal steps fill it: Dify workflow steps, MCP tool calls, and later framework adapters. Everything else leaves it `None`.
- The importer migrates `TraceRecord` onto `Trace` and fixes F3 in the same change.
- Secret scrubbing happens in the normalizer before persistence, the same as `observability/export.py` today.
- Storage: one `spans` table keyed by `(trace_id, span_id)` with a JSON `attributes` column. Traces link to `run_id`/`case_id` when they come from a Runport run.

---

## 4. MCP

### 4.1 Runport as MCP client (built: `connectors/mcp.py`)

Done: stdio and Streamable HTTP transports, version negotiation, paginated `tools/list`, `tools/call`, input-schema validation, tool latency separate from session setup, cancellation on timeout, `UNAVAILABLE` cost, secret redaction, 16 offline tests.

Remaining, in order:
1. Wire into `GenericRunner` via the workspace `targets:` section (M1), so it is reachable from CLI, API and SDK.
2. Emit each tool call as a `tool` span in `TargetResult.trajectory` (M2).
3. `resources/list|read` and `prompts/list|get` discovery, recorded as server capabilities. No benchmarking semantics yet.
4. Tool-sequence cases: a case lists several `{tool, arguments}` steps. This benchmarks scripted tool flows, still not agent decision-making.
5. Record and replay of MCP sessions to `REPLAYED` fixtures for regression tests.

Scope boundary: calling an MCP server's tools benchmarks the tool layer. Evaluating an agent that *uses* MCP needs the agent itself as the target (HTTP, SDK or framework adapter), with its tool calls captured as spans.

### 4.2 Runport as MCP server (proposed, `src/runport/mcp_server/`)

Transport: stdio (`runport mcp serve`) first, Streamable HTTP bound to `127.0.0.1` behind the existing `RUNPORT_API_TOKEN` middleware second. Implementation choice: the official `mcp` Python SDK as an optional extra (`runport[mcp]`). A server surface is larger than the client and the SDK tracks spec changes. The client keeps its zero-dependency implementation.

Every tool calls `runport.services`, never the CLI or HTTP layer.

| Tool | Service call | Side effects |
|---|---|---|
| `list_targets`, `inspect_target` | `ProjectService` | read |
| `list_datasets`, `validate_dataset` | `DatasetService` | read |
| `create_plan` | `ExperimentService.plan()`: returns fingerprint, cost ceiling, the authorization phrase, and an approval URL/command | writes a pending plan only |
| `run_replay` | `RunService.replay()` | `$0.00`, `REPLAYED` |
| `request_live_run` | `RunService.request_live(fingerprint)`: returns `pending_approval` unless an approver already granted that exact fingerprint | none until approved |
| `get_run`, `compare_runs`, `get_failures`, `get_trace` | `RunService`, `ResultStore` | read |
| `get_budget_status` | `BudgetService` | read |
| `export_report` | `ReportService` | writes under `reports/` |

Resources: `runport://targets`, `runport://datasets`, `runport://runs/{run_id}`, `runport://runs/{run_id}/traces/{case_id}`, `runport://schemas/target-result`, `runport://schemas/trace`.
Prompts: `benchmark_target`, `compare_candidates`, `investigate_failed_cases`, `audit_rag_pipeline`.

Security requirements (each needs a test):
- No tool can approve a plan, raise a ceiling, reconcile spend, or purge the ledger. `budget raise-pilot-ceiling` and `reconcile` stay CLI-only and interactive.
- `request_live_run` with a changed plan (different fingerprint) is rejected.
- Tool results pass through `scrub_secrets`, and datasets are returned as summaries unless the caller asks for case content.

---

## 5. Developer entry points

### 5.1 Workspace-declared targets (proposed, extends `core/workspace.py`)

```yaml
targets:
  support-agent:
    type: http_workflow
    url: http://localhost:8000/chat
    payload_template: {message: "{{query}}"}
    output_path: reply
    allow_localhost: true
    headers_from_env: {Authorization: SUPPORT_AGENT_TOKEN}   # values never stored in the file
  docs-tools:
    type: mcp
    command: [python, -m, docs_mcp]
```

A `build_target(name, spec)` factory in `connectors/registry.py` replaces the `if/elif` chain in `api/routes/targets.py`. Secrets are read from the environment by name only.

### 5.2 CLI (existing → proposed)

| Existing | Proposed | Notes |
|---|---|---|
| `init` | `init` (adds a `targets:` stub) | |
| (none) | `target list`, `target add`, `target check <name>` | `check` is a dry connection test. For billed targets it goes through the guard (fixes F2's twin in the CLI). |
| `validate-dataset` | keep; alias `dataset validate` | |
| `benchmark` (OpenRouter), `benchmark-rag` | `benchmark --target <name>` | Routes through `GenericRunner`. Explain-only by default, `--live` needs authorization, `--replay` stays. |
| `compare-runs` | keep; alias `compare` | |
| `export-traces`, `import-traces` | keep; `import-traces --format otel|openinference|langfuse` | |
| (none) | `report export <run> --format html|json|csv|junit` | |
| (none) | `mcp serve` | M3 |

### 5.3 Python SDK (proposed, `src/runport/sdk.py`, re-exported from `runport`)

```python
from runport import plan, run_replay, run_live

p = plan(target=my_callable_or_target_name, dataset="evals/agent.jsonl", scorers=["exact_match", "latency"])
print(p.fingerprint, p.max_cost_usd)
result = run_live(p, authorization=...)  # same LiveAuthorization as the CLI. Raises if absent or mismatched.
```

A bare Python callable is wrapped in `PythonCallableTarget`. There is no "run without a plan" shortcut for live targets.

### 5.4 REST API

Add `POST /api/plans` (exists as `/api/plan`), `POST /api/runs` for target runs through `GenericRunner`, `GET /api/runs/{id}/traces/{case}`. Change `POST /api/targets/test` to refuse billed target types unless a covering authorization exists, or restrict it to `UNAVAILABLE`-cost targets (F2).

### 5.5 TypeScript SDK

Thin client over the REST API (`@runport/sdk`). It ships after the REST surface in 5.4 is stable (M4), not before.

---

## 6. Capability registry (proposed, `connectors/registry.py`)

One Python table is the source of truth:

```python
ConnectorInfo(
    id="langgraph",
    module="connectors/langgraph.py",
    tier="experimental",
    integration="generic_http",  # native | generic_http | openai_compatible | sdk | trace_import | planned
    capabilities={"text"},
    cost_bases={"UNAVAILABLE", "ESTIMATED"},
)
```

- `tests/test_capability_registry.py` asserts that `README.md`, `docs/connectors.md`, `docs/connectors/README.md` and `web/src/data/connectors.ts` match it. It replaces the narrower `test_landing_connectors.py`.
- Every listed capability needs a contract test tagged with it. For example `per_step_trace` must have a test that asserts `trajectory` spans. F4 is fixed by dropping capabilities that fail this rule.
- `tier="stable"` requires passing `tests/test_connector_contracts.py`.

---

## 7. Evaluation scope per milestone

| Area | Exists | Add | Milestone |
|---|---|---|---|
| Output quality (EM, F1, calibration, judge) | `scorers/` | none | — |
| Performance (latency percentiles) | `scorers/performance.py` | tool-latency percentiles from spans | M2 |
| Cost per successful case | ledger + `TargetResult` | report column | M1 |
| Tool use: valid args, error and timeout rate, unnecessary calls | none | `scorers/tools.py` over `tool` spans | M2 |
| Trajectory: expected tool sequence, recovery after error | none | `scorers/trajectory.py` (exact, subsequence, set match) | M2 |
| Handoffs / multi-agent | none | handoff spans + scorer | M5 |
| RAG retrieval vs generation | `rag/` | span-level retrieval scoring | M4 |
| Safety (injection, leakage) | redaction only | later, separate design | M6 |

Supervised metrics still require human-approved ground truth (invariant 8). Trajectory expectations count as ground truth only when annotated and approved through `annotate`.

---

## 8. Milestones

Each milestone ends with `uv run pytest`, plugin tests, ruff, format and mypy green, and no socket access in tests.

| Milestone | Scope | New / changed files | Exit tests |
|---|---|---|---|
| **M0 Integrity** | F2, F3, F4, F5, F6 | `api/routes/targets.py`, `traces/models.py`, `traces/importer.py`, connector docs, `docs/ARCHITECTURE.md`, `connectors/registry.py` | `test_targets_test_route_requires_authorization`, `test_trace_missing_telemetry_is_none`, `test_capability_registry` |
| **M1 Bring your target** | Workspace `targets:`, `build_target`, `runport.services`, `benchmark --target` via `GenericRunner`, MCP target wired in, cost-per-success in reports | `core/workspace.py`, `connectors/registry.py`, `services/*.py`, `cli/commands/benchmarks.py`, `cli/commands/targets.py` | e2e: an HTTP target and an MCP fixture target, each benchmarked from the CLI in explain, replay and live (fake transport) modes, with a ledger entry per live case |
| **M2 Trajectories** | `traces/schema.py`, `spans` table, `TargetResult.trajectory`, MCP and Dify emit spans, tool and trajectory scorers | `traces/schema.py`, `storage/db.py`, `connectors/mcp.py`, `connectors/dify.py`, `scorers/tools.py`, `scorers/trajectory.py` | span persistence round-trip; scorer unit tests; secret scrubbing on span attributes |
| **M3 Runport MCP server** | Section 4.2 | `mcp_server/`, `cli/commands/mcp.py`, `pyproject.toml` extra `mcp` | in-process MCP client tests: each tool, plus refusal tests (approval, ceiling, fingerprint change) |
| **M4 SDK, API, CI** | Python SDK, REST target runs, JUnit report, a GitHub Action example, TS SDK over REST | `sdk.py`, `api/routes/runs.py`, `reports/junit.py`, `examples/ci/` | SDK e2e with `PythonCallableTarget`; JUnit schema test |
| **M5 Trace interoperability** | OTel/OpenInference import, LangGraph native adapter (stream events → spans), Langfuse/LangSmith import with provenance | `traces/otel.py`, `traces/openinference.py`, `connectors/langgraph.py` | fixture-based importer tests; LangGraph `per_step_trace` contract test |
| **M6 Framework and safety breadth** | CrewAI, OpenAI Agents SDK, PydanticAI adapters as plugins; safety evaluations | `examples/plugins/` or separate packages | per-adapter contract tests |

Native provider adapters (Anthropic, Gemini, Bedrock, Azure) are scheduled after M1, each behind the same contract suite. OpenAI-compatible services stay on `openai_compat`.

---

## 9. Open decisions

1. **`require_priced` default.** The code and DECISIONS.md say `false`. The strategy says the approved policy was `true`. Pick one and update `core/workspace.py`, the `init` template and DECISIONS.md together.
2. **`POST /api/targets/test` (F2).** Either restrict it to non-billed targets, or put it fully behind plan and authorization.
3. **MCP server dependency.** Should the server use the optional `mcp` SDK extra (recommended above) or reuse the hand-written JSON-RPC layer?
4. **Workflow connectors' tier.** Should Flowise, Langflow and n8n be relabelled `generic_http` (honest today), or kept as `experimental` native with their unbacked capabilities removed?

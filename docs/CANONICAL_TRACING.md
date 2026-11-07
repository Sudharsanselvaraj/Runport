# Runport Canonical Tracing Architecture

**Milestone 2 — Phase 1: Canonical Trace & Span Data Models and SQLite Persistence**

---

## 1. Overview & Objectives

Runport's canonical tracing foundation provides a provider-independent, durable representation of LLM, tool, retrieval, and multi-agent workflow executions.

Unlike ephemeral logging or external SaaS-bound trace formats, Runport's trace domain enforces strict architectural invariants:
- **Local-first, durable persistence**: SQLite WAL-backed tables (`traces` and `spans`) with transactional integrity.
- **Strict telemetry semantics**: "Null is not 0" — unmeasured values remain `None`, never converted to zero.
- **Provable hierarchy**: Explicit acyclic parent-child trees with cross-trace isolation.
- **Automatic secret scrubbing**: All errors, attributes, and events are sanitized recursively before reaching storage.

---

## 2. Canonical Data Models (`runport.traces.domain`)

The domain models are implemented using **Pydantic v2**:

### SpanKind (Enum)
Categorizes units of execution:
- `llm`: Single model invocation (e.g. OpenAI, Anthropic, OpenRouter, Ollama).
- `tool`: Single tool execution (e.g. MCP tool call, custom Python tool).
- `retrieval`: Vector database search, document retrieval, or knowledge query.
- `workflow_step`: Pipeline node in orchestrated graphs (e.g. Dify, LangGraph, n8n).
- `agent`: Autonomous agent or sub-agent execution context.
- `handoff`: Control transition between specialized agents.
- `rerank`: Search result reranking evaluation.
- `router`: Classification or model routing step.
- `other`: Catch-all for unclassified steps.

### SpanStatus (Enum)
Execution status tracking:
- `ok`: Successful execution.
- `error`: Execution failed (error sanitized and persisted).
- `timeout`: Operation timed out.
- `cancelled`: Aborted by budget guard, privacy gate, or user interrupt.
- `unset`: In-progress or unfinalized state.

### SpanEvent
Point-in-time timestamped events within a span:
- `name`: str (e.g. `token_chunk`, `cache_hit`, `schema_validation`).
- `timestamp`: UTC timezone-aware `datetime`.
- `attributes`: Sanitized key-value metadata.

### Span
An individual execution span:
- `trace_id`: Foreign key referencing the parent `Trace`.
- `span_id`: Unique identifier within the trace.
- `parent_span_id`: Optional parent span identifier (enforces tree hierarchy).
- `name`: Descriptive operation name.
- `kind`: `SpanKind`.
- `status`: `SpanStatus` (default: `UNSET`).
- `start_time`: Optional UTC `datetime`.
- `end_time`: Optional UTC `datetime`.
- `duration_ms`: Optional measured millisecond duration (`>= 0.0`).
- `provider`: Optional provider string (e.g. `openrouter`, `dify`).
- `model`: Optional model string (e.g. `anthropic/claude-3.5-sonnet`).
- `prompt_tokens`: Optional integer (`>= 0`, `None` if unmeasured).
- `completion_tokens`: Optional integer (`>= 0`, `None` if unmeasured).
- `total_tokens`: Optional integer (`>= 0`, `None` if unmeasured).
- `cost_usd`: Optional decimal string (`>= 0`, `None` if unmeasured).
- `cost_basis`: Provenance vocabulary (`ACTUAL`, `ESTIMATED`, `UNRESOLVED`, `UNAVAILABLE`).
- `attributes`: Structured attributes (scrubbed of secrets).
- `events`: Ordered list of `SpanEvent`.
- `error`: Sanitized error message if failed.
- `attempt`: Retry attempt counter (`>= 1`, default 1).
- `source`: Execution provenance (`native`, `instrumented`, `otel`, `replay`, etc.).
- `created_at`: UTC timestamp.

### Trace
The root container representing an execution tree:
- `trace_id`: Primary key identifier.
- `run_id`: Optional foreign key referencing `evaluation_runs(run_id)`.
- `case_id`: Optional benchmark dataset case identifier.
- `target_id`: Optional target route identifier.
- `session_id`: Optional interactive conversation session ID.
- `name`: Descriptive name.
- `status`: Overall `SpanStatus`.
- `start_time` / `end_time`: UTC timestamps.
- `attributes`: Sanitized trace-level metadata.
- `schema_version`: Revision integer (default 1).
- `spans`: Ordered child spans validating hierarchy, acyclicity, and cross-trace isolation.

---

## 3. Strict Telemetry & Security Invariants

### 1. "Null is not 0"
- Telemetry that was not legitimately reported or measured (latency, prompt tokens, completion tokens, monetary cost) remains `None` (`NULL` in SQLite).
- A legitimately measured `0` (e.g. 0 completion tokens on refusal, 0.0ms local cache hit, $0.00 local model cost) is stored as `0` / `"0.000000"` and remains distinguishable from missing data.

### 2. Timezone-Aware UTC Timestamps
- All timestamps (`start_time`, `end_time`, `timestamp`, `created_at`) are validated and normalized to UTC (`tzinfo=timezone.utc`).
- Inverted timestamps (`end_time < start_time`) are strictly rejected with validation errors.

### 3. No Duration Fabrication
- Durations are never fabricated from incomplete or missing timestamps. If either `start_time` or `end_time` is absent and `duration_ms` was not reported, `duration_ms` remains `None`.

### 4. Rejection of Invalid Negative Telemetry
- Negative token counts (`< 0`), negative durations (`< 0.0`), and negative costs (`< 0`) are rejected immediately by domain validators.

### 5. Parent-Child Hierarchy & Cross-Trace Isolation
- Self-referential parents (`parent_span_id == span_id`) are rejected.
- Spans belonging to a different trace (`span.trace_id != trace.trace_id`) are rejected with cross-trace isolation errors.
- Referenced parent spans must exist within the trace; cyclic parentage is detected and rejected.

### 6. Automatic Secret Scrubbing
- Strings, errors, dictionary attributes, and event payloads are sanitized via `runport.providers.base.scrub_secrets`.
- Bearer tokens, OpenAI/OpenRouter API keys (`sk-...`, `sk-or-v1-...`), and sensitive keys (`auth`, `token`, `secret`, `key`, `password`) are scrubbed before persistence.

---

## 4. SQLite Persistence & Migration Strategy

### SQLite WAL Schema
Persistence is managed via `DatabaseManager` and `TraceRepository`:

```sql
CREATE TABLE IF NOT EXISTS traces (
    trace_id TEXT PRIMARY KEY,
    run_id TEXT,
    case_id TEXT,
    target_id TEXT,
    session_id TEXT,
    name TEXT NOT NULL,
    status TEXT NOT NULL,
    start_time TEXT,
    end_time TEXT,
    attributes_json TEXT NOT NULL DEFAULT '{}',
    schema_version INTEGER NOT NULL DEFAULT 1,
    source TEXT NOT NULL DEFAULT 'native',
    source_ref TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY (run_id) REFERENCES evaluation_runs(run_id)
);

CREATE TABLE IF NOT EXISTS spans (
    trace_id TEXT NOT NULL,
    span_id TEXT NOT NULL,
    parent_span_id TEXT,
    name TEXT NOT NULL,
    kind TEXT NOT NULL,
    status TEXT NOT NULL,
    start_time TEXT,
    end_time TEXT,
    duration_ms REAL,
    provider TEXT,
    model TEXT,
    prompt_tokens INTEGER,
    completion_tokens INTEGER,
    total_tokens INTEGER,
    cost_usd TEXT,
    cost_basis TEXT,
    attributes_json TEXT NOT NULL DEFAULT '{}',
    events_json TEXT NOT NULL DEFAULT '[]',
    error_json TEXT,
    attempt INTEGER NOT NULL DEFAULT 1,
    source TEXT NOT NULL DEFAULT 'native',
    created_at TEXT NOT NULL,
    PRIMARY KEY (trace_id, span_id),
    FOREIGN KEY (trace_id) REFERENCES traces(trace_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_traces_run_id ON traces(run_id);
CREATE INDEX IF NOT EXISTS idx_traces_run_case ON traces(run_id, case_id);
CREATE INDEX IF NOT EXISTS idx_traces_status ON traces(status);
CREATE INDEX IF NOT EXISTS idx_traces_start_time ON traces(start_time);
CREATE INDEX IF NOT EXISTS idx_spans_trace ON spans(trace_id);
CREATE INDEX IF NOT EXISTS idx_spans_parent ON spans(trace_id, parent_span_id);
CREATE INDEX IF NOT EXISTS idx_spans_kind ON spans(trace_id, kind);
CREATE INDEX IF NOT EXISTS idx_spans_status ON spans(status);
CREATE INDEX IF NOT EXISTS idx_spans_start_time ON spans(start_time);
```

### Safe Migration v4
- Migration version 4 is tracked in `schema_migrations`.
- The migration is 100% additive: `CREATE TABLE IF NOT EXISTS` and index creation.
- Pre-existing user databases with historical `evaluation_runs`, `evaluation_results`, and `budget_ledger` transactions remain completely untouched without data rewrite.

---

## 5. Scope Boundary: Phase 1 vs Future Phases

| Component | Status | Notes |
|:---|:---|:---|
| Canonical `Span`, `Trace`, `SpanKind`, `SpanStatus` models | **Implemented (Phase 1)** | Pydantic v2 domain models |
| SQLite `traces` and `spans` tables and indexes | **Implemented (Phase 1)** | WAL mode, FK cascade |
| `DatabaseManager` trace/span CRUD & atomic rollbacks | **Implemented (Phase 1)** | Fully tested |
| `TraceRepository` typed repository interface | **Implemented (Phase 1)** | Re-exported in `runport.traces` |
| Safe additive migration (v4) | **Implemented (Phase 1)** | Verified against legacy databases |
| `GenericRunner` runtime span instrumentation | **Implemented (Phase 2)** | Automatic Trace and root Span per case |
| Target-specific span extraction (Dify, MCP, RAG) | **Implemented (Phase 2)** | `per_step_trace`, MCP tool calls, RAG retrieval |
| `TargetResult.trajectory` field | **Implemented (Phase 2)** | Typed `Span` sequence container |
| Trajectory evaluators (`ToolSelectionScorer`, `ToolArgumentScorer`, `LoopDetectionScorer`, `StepBudgetScorer`, `RecoveryScorer`) | **Implemented (Phase 3)** | `runport.scorers.tools`, `runport.scorers.trajectory` |
| Terminal Tree/Panel View & CLI (`runport trace`, `runport traces`) | **Implemented (Phase 4)** | Rich tree, panel, table |
| Web Dashboard Trace Waterfall / Tree View & REST API | **Implemented (Phase 4)** | Interactive React Gantt timeline & inspector drawer |
| OTLP Export & OpenInference Interoperability | **Implemented (Phase 5)** | `runport.traces.otlp`, REST OTLP endpoints, CLI import/export |

---

## 6. OpenTelemetry & OpenInference Interoperability (`runport.traces.otlp`)

Milestone 2 - Phase 5 provides full two-way interoperability with standard OpenTelemetry and OpenInference protocols:

### Ingestion (`OtlpIngester`)
- Accepts standard OTLP JSON trace payloads (`ExportTraceServiceRequest`).
- Maps GenAI semantic conventions (`gen_ai.system`, `gen_ai.request.model`, `gen_ai.usage.input_tokens`, etc.) and OpenInference conventions (`openinference.span.kind`) into Runport canonical `Trace` and `Span` models.
- Guarantees strict invariants:
  - **Null is not 0**: Unreported tokens, cost, or duration remain `None`.
  - **Zero secret leakage**: All attributes, events, errors, inputs, and outputs pass through recursive secret scrubbing (`scrub_secrets`).
  - **Hierarchy preservation**: Orphan parents are detached gracefully, and timestamps are normalized to UTC.

### Export (`OtlpExporter`)
- Converts canonical Runport `Trace` and `Span` trees into standard OTLP JSON format.
- Emits W3C-compliant 32-hex trace IDs and 16-hex span IDs.
- Preserves token counts, spend basis, and custom attributes.

### REST Endpoints & CLI
- `POST /api/traces/otlp` & `POST /api/v1/traces/otlp`: Ingests OTLP JSON payloads.
- `GET /api/traces/{trace_id}/otlp`: Exports canonical trace in OTLP JSON format.
- CLI:
  - `runport import-otlp <file.json>`
  - `runport export-otlp <trace_id> [-o <out.json>]`


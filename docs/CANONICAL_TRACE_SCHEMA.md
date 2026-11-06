# Canonical Trace Schema

**Status: design.** Nothing in this document exists in code yet, except where marked "existing". It is the prerequisite (F1) for
per-step tracing, trajectory evaluation, OpenTelemetry ingestion, Langfuse export and framework instrumentation.

---

## 1. Why one schema

Runport currently has four unlinked shapes for "what happened":

| Existing shape | File | Linked to runs? |
|:---|:---|:---|
| `evaluation_runs` / `evaluation_results` rows | `storage/db.py` | Yes (the run) |
| `TargetResult.metadata` (Dify nodes, MCP tool data, RAG retrieval) | `targets/base.py` | Only as untyped JSON in memory |
| `PredictionRecord` JSONL | `classification/records.py` | Own store |
| `RequestEvent` JSONL | `observability/events.py` | Not written by any executor |
| `TraceRecord` / `ObservationSpan` (imported) | `traces/models.py` | No |

The canonical model replaces none of the run tables. It adds spans that hang off a run case, and it is the single target for
native connectors, instrumentation, OTel ingestion and exports.

---

## 2. Model (Pydantic v2, `src/runport/traces/schema.py`)

Rules for every field: telemetry that was not reported is `None`, never `0`; text and attributes are scrubbed before storage.

```python
class SpanKind(str, Enum):
    AGENT = "agent"  # an agent or sub-agent invocation
    LLM = "llm"  # one model call
    TOOL = "tool"  # one tool call (MCP or framework tool)
    RETRIEVAL = "retrieval"
    RERANK = "rerank"
    HANDOFF = "handoff"  # control passes between agents
    ROUTER = "router"  # a routing decision
    WORKFLOW_STEP = "workflow_step"  # a node in Dify, LangGraph, n8n…
    OTHER = "other"


class SpanStatus(str, Enum):
    OK = "ok"
    ERROR = "error"
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"
    UNSET = "unset"


class Span(BaseModel):
    span_id: str
    parent_span_id: Optional[str] = None
    trace_id: str
    kind: SpanKind
    name: str
    started_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None
    latency_ms: Optional[float] = None  # measured or reported; None if neither
    status: SpanStatus = SpanStatus.UNSET
    error: Optional[str] = None  # scrubbed
    attempt: int = 1  # retries are separate spans with attempt > 1
    attributes: Dict[str, Any] = {}  # kind-specific, see section 3
    source: Literal["native", "instrumented", "otel", "openinference", "langfuse_import", "replay"]


class Trace(BaseModel):
    trace_id: str
    run_id: Optional[str] = None  # set for traces produced by a Runport run
    case_id: Optional[str] = None
    session_id: Optional[str] = None
    source: str  # same vocabulary as Span.source
    source_ref: Optional[str] = None  # e.g. the OTel trace id or Langfuse trace id
    started_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None
    spans: List[Span]
    final_output: Optional[str] = None
```

---

## 3. Kind-specific attributes

Names follow the OpenTelemetry GenAI semantic conventions where one exists, so OTel spans map without renaming.

| Kind | Attributes |
|:---|:---|
| `llm` | `gen_ai.system`, `gen_ai.request.model`, `gen_ai.response.model`, `gen_ai.usage.input_tokens`, `gen_ai.usage.output_tokens`, `runport.cost_usd`, `runport.cost_basis` (`ACTUAL`/`ESTIMATED`/`UNRESOLVED`/`UNAVAILABLE`), `gen_ai.response.finish_reasons` |
| `tool` | `gen_ai.tool.name`, `gen_ai.tool.call.id`, `runport.tool.arguments` (scrubbed, size-capped), `runport.tool.result` (scrubbed, size-capped), `runport.tool.schema_valid`, `runport.tool.server` (e.g. MCP server id) |
| `agent` | `gen_ai.agent.name`, `gen_ai.agent.id` |
| `handoff` | `runport.handoff.from_agent`, `runport.handoff.to_agent`, `runport.handoff.reason` |
| `router` | `runport.route.options`, `runport.route.chosen` |
| `retrieval` | `runport.retrieval.query`, `runport.retrieval.doc_ids`, `runport.retrieval.scores`, `runport.retrieval.k` |

Cost lives only on `llm` spans (and tools that report a price). A trace's cost is the sum of known span costs **plus** a count of
spans whose cost is unknown; it is never reported as a total that silently treats unknown as zero.

---

## 4. Storage

Two tables in the existing SQLite database (and the future Postgres schema):

```sql
CREATE TABLE traces (
  trace_id TEXT PRIMARY KEY, run_id TEXT REFERENCES evaluation_runs(run_id), case_id TEXT,
  session_id TEXT, source TEXT NOT NULL, source_ref TEXT,
  started_at TEXT, ended_at TEXT, final_output TEXT
);
CREATE TABLE spans (
  trace_id TEXT NOT NULL REFERENCES traces(trace_id), span_id TEXT NOT NULL, parent_span_id TEXT,
  kind TEXT NOT NULL, name TEXT NOT NULL, started_at TEXT, ended_at TEXT, latency_ms REAL,
  status TEXT NOT NULL, error TEXT, attempt INTEGER NOT NULL DEFAULT 1,
  attributes_json TEXT NOT NULL, source TEXT NOT NULL,
  PRIMARY KEY (trace_id, span_id)
);
CREATE INDEX idx_spans_kind ON spans(trace_id, kind);
```

Spend stays in `budget_ledger`. Span costs are informational and must reconcile to the ledger for native runs (test).

---

## 5. Scores linked to traces

```python
class ScoreKind(str, Enum):
    GROUND_TRUTH = "ground_truth"  # compared with a human-approved reference
    JUDGE = "judge"  # LLM-as-judge; records judge model and rubric hash
    HEURISTIC = "heuristic"  # lexical overlap, regex, length, etc.


class Score(BaseModel):
    score_id: str
    name: str  # e.g. "answer_correctness", "tool_selection"
    kind: ScoreKind
    value: Optional[float]  # None = not measurable for this case
    target: Literal["case", "trace", "span"]
    trace_id: Optional[str] = None
    span_id: Optional[str] = None
    evidence: Optional[str] = None
    evaluator: str  # scorer id and version
```

Reports and UIs must label every score with its kind. Model agreement is never stored as `GROUND_TRUTH`.

---

## 6. Producers and mappings

| Producer | How it fills `Trace` |
|:---|:---|
| `GenericRunner` (all native runs) | One trace per case; an `llm` or `workflow_step` root span from `TargetResult` |
| `connectors/dify.py` (workflow mode) | `workflow_step` span per `node_finished` event |
| `connectors/mcp.py` | `tool` span per `tools/call`, with schema validation result |
| `rag/target.py` | `retrieval` span, then `llm` span |
| LangGraph adapter (planned) | `workflow_step` per node from the streaming run events |
| OTel / OpenInference ingest (planned) | Map GenAI and OpenInference attributes to section 3 |
| `traces/importer.py` (existing, Langfuse-style files) | `GENERATION` → `llm`, `SPAN` → `other`/`workflow_step`, `latency` seconds → ms |
| Langfuse export (planned) | Inverse of the import mapping, via the Langfuse public ingestion API |

---

## 7. Acceptance tests

- Round trip: build → store → load returns an equal `Trace`.
- Null semantics: a span with no reported tokens or latency stores `NULL` and reports "unavailable".
- Redaction: a header token or env secret in tool arguments never reaches `spans.attributes_json`.
- Cost reconciliation: for native runs, the sum of known span costs equals the ledger's booked amount for that run.
- OTel fixture: a recorded GenAI OTLP payload maps to the expected spans.

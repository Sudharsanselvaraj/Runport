# Changelog

All notable changes to Runport are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.1] - 2026-11-09

### Security & Reliability Hardening
- **Strict Multi-Tenant Resource Isolation**:
  - Enforced project-level authorization across runs, results, traces, plans, and asynchronous jobs.
  - Cross-tenant resource queries return `404 Not Found` fail-closed to prevent resource enumeration.
  - SQL-level tenant scoping applied before loading spans and trace records.
- **Durable Asynchronous Worker Leases & Recovery**:
  - Implemented lease expiration and heartbeat tracking (`worker_id`, `lease_expires_at`, `heartbeat_at`) in `run_jobs` table.
  - Background worker thread renews active leases every 15 seconds.
  - Automatic stale job recovery sweeps abandoned worker reservations and marks dead executions failed.
  - Cooperative cancellation checked at case execution boundaries.
- **Financial Concurrency & Execution Integrity**:
  - Additive SQLite Migration 8: added `idempotency_key` column on `run_jobs` with unique partial index, and `project_id` on `budget_reservations`.
  - Atomically reserved budget per case during concurrent execution, releasing held reservations immediately upon case completion or failure.
  - Deterministic financial transaction IDs (`tx-{run_id}-{case_id}`) with `INSERT OR IGNORE` semantics preventing duplicate spend booking.
- **Control-Plane MCP Parity**:
  - Added `get_budget_status`, `list_jobs`, and `cancel_job` MCP tools.
  - Strictly forbade agent self-approvals, preserving human confirmation requirements.
- **SDK Multi-Tenant & Idempotency Support**:
  - Extended Python SDK `plan()` and `benchmark()` with `project_id`.
  - Added `X-Project-Id` and `Idempotency-Key` headers to TypeScript SDK `RunportClient`.

## [1.0.0] - 2026-11-09

### Added
- **Universal Developer Instrumentation API (`runport.instrumentation`)**:
  - `@trace` decorator for synchronous and asynchronous Python functions, agents, and tool calls.
  - Context managers `start_trace()` and `start_span()` with `contextvars` hierarchical span tracking.
  - LLM client wrappers `wrap_openai()` and `wrap_anthropic()` extracting exact token metrics and outputs as canonical child spans.
- **Framework Interoperability**:
  - OpenTelemetry (OTel) GenAI Semantic Conventions and OpenInference trace ingestion & export (`POST /api/v1/traces/otlp`, `runport import-otlp`, `runport export-otlp`).
  - Bidirectional Langfuse v2 batch export & import (`POST /api/v1/traces/langfuse/export`, `POST /api/v1/traces/langfuse/import`, `runport export-langfuse`, `runport import-langfuse`).
  - Native LangGraph SSE streaming adapter (`LangGraphStreamingConnector`) and in-process callback tracer (`RunportLangGraphTracer`).
- **Production-Grade Model Context Protocol (MCP)**:
  - Streamable HTTP (SSE) transport (`GET /mcp/sse`, `POST /mcp/messages`) supporting protocol revisions up to `2026-07-28`.
  - Bearer token authentication and strict self-approval prevention.
  - Ready-to-use agent IDE blueprints for Claude Desktop, Cursor, and VS Code.
- **Hosted Multi-Tenancy & RBAC (`docs/MULTI_USER_SECURITY_MODEL.md`)**:
  - Additive SQLite Migration 6: `organizations`, `projects`, `memberships`, and `audit_log` tables.
  - Project-scoped filtering across API keys, runs, traces, and ledger records.
  - Granular RBAC permissions for `VIEWER`, `MEMBER`, `APPROVER`, `ADMIN`.
  - Fail-closed self-approval guard blocking principals from approving their own billable plans.
- **Versioned REST API v1 & SDKs**:
  - OpenAPI 3.1 REST API v1 (`/api/v1/`) with typed Pydantic v2 schemas and RFC-7807 error envelopes.
  - Asynchronous background job worker (`JobManager`) with non-blocking execution and cancellation.
  - Remote Python client (`runport.Client`) with retry handling and typed exceptions.
  - Standalone TypeScript SDK package (`@runport/sdk`).
- **Canonical Tracing & Trajectory Evaluation**:
  - Pydantic v2 `Trace` and `Span` models enforcing Invariant #1 ("Null is not 0").
  - SQLite WAL persistence with indexes for trace hierarchy and parent-child span trees.
  - Interactive web waterfall visualization (`TraceView.tsx`) and collapsible TUI trace tree.
- **Automated GA Release Gates (`tests/test_release_gates_v1.py`)**:
  - 6 automated release gates verifying package cleanliness, offline hermeticity, fail-closed spend caps under concurrency, cryptographic tamper detection, null integrity, and secret redaction.

## [0.1.0] - 2026-11-03

### Added
- **Universal Target Execution**: Unified `Target` abstraction with connectors for `openai_compat`, `openrouter`, `dify`, `http_workflow`, `python_target`, and `ollama`.
- **Preflight Plan Fingerprint**: Cryptographic SHA-256 fingerprint binding models, endpoint routes, dataset hash, prompt template hash, and budget caps prior to live execution.
- **Fail-Closed Spend Ledger**: Append-only SQLite WAL ledger tracking spend with strict provenance vocabulary (`ACTUAL`, `ESTIMATED`, `UNRESOLVED`, `UNAVAILABLE`). Unresolved spend halts subsequent runs fail-closed.
- **Strict Ground Truth Verification**: Supervised evaluation metrics (Accuracy, Balanced Accuracy, Precision, Recall, Macro F1, Wilson 95% confidence intervals, Cohen's Kappa, and Confusion Matrices) strictly evaluated against human ground truth.
- **Local Read-Only Interfaces**:
  - Full-screen Rich Terminal User Interface (`runport ui`) with live histograms and monitor panes.
  - Interactive launcher and workflow menu (`runport`).
  - Local web dashboard (`runport web`) built with FastAPI, React, TypeScript, and Vite, served strictly on localhost.
- **Sanitized Trace Exports**: Zip/JSON trace exporters with automatic scrubbing of API keys, bearer tokens, and sensitive security identifiers (`runport export-traces`).
- **Offline Replay Runner**: Zero-cost, isolated replay harness (`REPLAYED` provenance, `$0.00` spend) for deterministic quickstart demos and contract testing.

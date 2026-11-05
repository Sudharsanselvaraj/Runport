# Runport Roadmap Release Plan (v0.1.0 → v1.0.0)

> **Status**: Approved Roadmap Strategy  
> **Horizon**: v0.1.0 Baseline → v1.0.0 General Availability  
> **Document Ref**: `RUNPORT-SPEC-006`  
> **Author**: Runport Architecture & Engineering Team  

---

## 1. Release Philosophy & Milestone Structure

To transition Runport from a local-first alpha benchmark tool (`v0.1.0`) into the definitive open-source universal LLM and workflow benchmarking platform (`v1.0.0`), engineering follows a strict milestone strategy.

Each milestone enforces three non-negotiable delivery gates:
1. **Architectural Invariant Integrity**: Zero regressions against the 10 core invariants in `AGENTS.md` (e.g., *Null is not 0*, *Fail-Closed Budgeting*, *Strict Runner Guard Order*).
2. **Offline-First Verification**: 100% of automated unit, contract, and invariant tests execute offline with blocked sockets and deterministic test doubles.
3. **No Phantom Capabilities**: Public documentation, SDK types, and CLI interfaces only expose fully implemented, tested features.

```mermaid
gantt
    title Runport v0.1.0 to v1.0.0 Release Trajectory
    dateFormat  YYYY-MM
    section Core Infrastructure
    v0.1.0 Alpha Baseline (Current)         :done, m0, 2026-11, 2026-11
    M1: Universal Execution Consolidation   :active, m1, 2026-11, 2026-12
    section Ecosystem & Tooling
    M2: Public Python & TypeScript SDKs     :m2, 2026-12, 2027-01
    M3: Model Context Protocol (MCP) Server :m3, 2027-01, 2027-02
    section Advanced Observability
    M4: Step Tracing & Trajectory Scoring   :m4, 2027-02, 2027-03
    section Enterprise Security
    M5: Multi-User Hosting & RBAC           :m5, 2027-03, 2027-04
    section General Availability
    M6: Universal Platform GA v1.0.0        :m6, 2027-04, 2027-05
```

---

## 2. Detailed Milestone Specifications

### Milestone 1: Universal Execution Consolidation (v0.2.0)
- **Primary Objective**: Eliminate the Dual Execution Path vulnerability, replace in-memory approval tokens with durable SQLite records, and introduce the Canonical Trace Schema v2.
- **Key Deliverables**:
  - `src/runport/runs/service.py`: Consolidated `ExecutionService` enforcing the 7-step runner guard pipeline across all callers.
  - Refactor `src/runport/api/routes/runs.py` and `src/runport/cli.py` to invoke `ExecutionService`.
  - SQLite table `plan_approvals` with atomic WAL token consumption and TTL verification.
  - Pydantic models for `AgentTrajectory`, `AgentStep`, and `StepAttribution` in `src/runport/traces/models.py`.
- **Architectural Prerequisites**:
  - Implementation of `RUNPORT-SPEC-001` (Universal Execution) and `RUNPORT-SPEC-002` (Canonical Trace Schema).
- **Verification & Acceptance Gates**:
  - Automated concurrency test verifying that two parallel requests cannot reuse the same approval token.
  - Verification that process restarts preserve pending and consumed approval states.
  - 100% test pass across all existing 389 core offline tests.

---

### Milestone 2: Public SDKs — Python & TypeScript (v0.3.0)
- **Primary Objective**: Provide public, typed developer libraries for programmatically managing benchmarks, budgets, and datasets.
- **Key Deliverables**:
  - Python SDK: `runport.Client` and `runport.AsyncClient` published to PyPI.
  - TypeScript SDK: `@runport/sdk` published to npm with isomorphic fetch support.
  - Automated OpenAPI code-generation pipeline ensuring zero SDK-API drift.
  - Custom typed exception hierarchies for budget cap violations and approval gates.
- **Architectural Prerequisites**:
  - M1 Execution Service stabilization.
  - REST API routes frozen and documented via OpenAPI 3.1.
- **Verification & Acceptance Gates**:
  - End-to-end Python SDK contract tests executing offline against a mock FastAPI server.
  - TypeScript SDK test suite passing in Node.js 18+, Bun, and simulated browser runtimes.
  - Clean documentation and sample scripts for both languages.

---

### Milestone 3: Model Context Protocol (MCP) Server (v0.4.0)
- **Primary Objective**: Enable AI assistants (Claude Desktop, Cursor, Antigravity) to act as benchmark orchestrators under strict spend governance.
- **Key Deliverables**:
  - `src/runport/mcp/server.py`: FastMCP server supporting `stdio` and `sse` transports.
  - MCP Tools: `runport_create_execution_plan`, `runport_run_benchmark`, `runport_approve_plan`, `runport_get_budget_status`, `runport_validate_dataset`.
  - MCP Resources: `runport://runs/{run_id}`, `runport://traces/{trace_id}`, `runport://budget/status`.
  - MCP Prompts: `benchmark_evaluation_review`, `dataset_leakage_audit`.
  - Fail-closed security gate preventing autonomous agents from self-approving spend cap breaches.
- **Architectural Prerequisites**:
  - M1 Execution Service and durable approval lifecycle.
- **Verification & Acceptance Gates**:
  - Automated MCP tool invocation tests via JSON-RPC stdio harness.
  - Invariant test: Untrusted MCP agent invocation fails closed when estimated spend exceeds budget cap without signed human token.

---

### Milestone 4: Native Step Tracing, Trajectory Scoring & Interoperability (v0.5.0)
- **Primary Objective**: Expand Runport from black-box evaluation to granular agent trajectory scoring and open telemetry interoperability.
- **Key Deliverables**:
  - Native LangGraph callback handler capturing per-node token spend, latency, and state deltas.
  - Trajectory evaluation scorers in `src/runport/scorers/trajectory.py`:
    - `ToolSelectionF1`: Precision and recall of tool choices.
    - `PlanAdherenceScore`: Alignment with gold execution paths.
    - `RedundantToolCallIndex`: Measurement of agent thrashing.
  - OTLP trace ingestion endpoint `/api/v1/traces/otlp/v1/traces`.
  - Direct Langfuse v2 export pipeline in `src/runport/observability/export.py`.
- **Architectural Prerequisites**:
  - Canonical Trace Schema v2 (`RUNPORT-SPEC-002`).
- **Verification & Acceptance Gates**:
  - Multi-agent LangGraph workflow benchmarked with node-level spend attribution.
  - Round-trip trace export test: `Runport Trace` $\to$ `Langfuse JSON` $\to$ `Runport Trace` without telemetry degradation.

---

### Milestone 5: Multi-User Hosting & Scoped Security Model (v0.6.0)
- **Primary Objective**: Enable secure multi-tenant team and enterprise hosting.
- **Key Deliverables**:
  - Database tenancy migration supporting PostgreSQL 15+ and tenant-partitioned SQLite.
  - 3-tier hierarchy: Organization $\to$ Project $\to$ User.
  - Role-Based Access Control (RBAC): `Owner`, `Admin`, `Approver`, `Runner`, `Viewer`.
  - Scoped API keys (`rp_live_...`) with SHA-256 storage, expiration, and last-used tracking.
  - Append-only security audit log table (`security_audit_log`).
- **Architectural Prerequisites**:
  - Specification `RUNPORT-SPEC-005` (Multi-User Security Model).
- **Verification & Acceptance Gates**:
  - RBAC permission matrix verified by exhaustive unit tests.
  - Invariant test: Zero cross-tenant data leakage between isolated project API keys.
  - Audit log invariant: Security-critical actions produce immutable records.

---

### Milestone 6: Universal Platform General Availability (v1.0.0 GA)
- **Primary Objective**: Deliver the battle-tested, enterprise-ready universal benchmarking platform.
- **Key Deliverables**:
  - Universal framework callbacks for LangChain, LlamaIndex, CrewAI, AutoGen, and Semantic Kernel.
  - Production Docker containers and Helm deployment charts.
  - Web UI enhancements: Live trajectory graph visualizer, confusion matrix drill-downs, team budget management.
  - Comprehensive documentation site and production deployment guides.
- **Architectural Prerequisites**:
  - Successful completion and validation of Milestones M1 through M5.
- **Verification & Acceptance Gates**:
  - Over 1,000 automated offline tests passing with 0 failures and 0 warnings.
  - Security audit and penetration test verification.
  - Zero unpriced runs permitted without explicit provenance tagging.

---

## 3. Milestone Summary Matrix

| Milestone | Target Version | Primary Focus | Blocker Addressed | Expected Test Count |
| :--- | :---: | :--- | :--- | :---: |
| **M1** | `v0.2.0` | Execution Consolidation & Approvals | Dual Execution Engines & Volatile Tokens | ~450 |
| **M2** | `v0.3.0` | Public Python & TypeScript SDKs | Missing Public Client SDKs | ~550 |
| **M3** | `v0.4.0` | MCP Server & Agent Ecosystem | Missing MCP Tools & Governance | ~650 |
| **M4** | `v0.5.0` | Step Tracing & Trajectory Scoring | Shallow Black-Box Workflow Evaluation | ~780 |
| **M5** | `v0.6.0` | Multi-User Security & RBAC | Single-Tenant Architecture Bottleneck | ~900 |
| **M6** | `v1.0.0` | Universal GA Platform | Full Enterprise Hardening & Callbacks | >1,000 |


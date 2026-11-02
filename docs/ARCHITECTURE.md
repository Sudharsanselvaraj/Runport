# System Architecture: Runport (`runport`)

**Status**: Universal Benchmarking Architecture  
**Date**: November 2026  
**License**: Apache 2.0  

---

## 1. Architectural Overview & Context

**Runport** is a universal, local-first open-source benchmarking platform engineered to evaluate any LLM, system prompt, autonomous agent, or orchestrated workflow (Dify, Flowise, Langflow, n8n, LangGraph, custom HTTP endpoints) on real datasets under hard, fail-closed spend caps.

The architecture decouples benchmarking into five fundamental layers:
1. **Target & Workflow Connector Layer**: Unified protocol for raw LLMs and multi-step orchestrated pipelines.
2. **Data & Privacy Gate Layer**: Schema-enforced case ingestion, salted-hash pseudonymization, and PII regex redaction.
3. **Execution & Budget Guard Layer**: Append-only SQLite WAL ledger, micro-dollar budget tracking, and interactive typed plan approval.
4. **Scoring & Statistical Verification Layer**: Supervised metrics computed strictly from human-approved ground-truth labels with Wilson CIs and bootstrap intervals.
5. **Observability & Presentation Layer**: Rich Terminal UI (TUI) dashboard, event lifecycle log, sanitized trace export, and FastAPI/React interfaces.

```mermaid
graph TB
    subgraph Targets["Target Pipelines & Providers"]
        OpenRouter["OpenRouter / Direct Model APIs"]
        DifyConn["Dify (Chat & SSE Streaming)"]
        WorkflowConns["Flowise / Langflow / n8n / LangGraph"]
        CustomHTTP["Custom HTTP Endpoints / Python Callables"]
    end

    subgraph CorePlatform["Runport Core Architecture"]
        DatasetIngest["Dataset Loader (JSONL / CSV)"] --> PrivacyGate["Data Gate & PII Redaction"]
        PrivacyGate --> BudgetGate["Budget Service & Fail-Closed Caps"]
        
        BudgetGate --> PlanReview["Interactive Typed Plan Approval"]
        PlanReview --> Executor["Benchmark Runner & Execution Engine"]
        
        Executor --> Targets
        Targets --> ResponseValidator["Output Validators & Scrubbers"]
        
        ResponseValidator --> Ledger["Append-Only SQLite WAL Ledger"]
        ResponseValidator --> EventTail["Request Lifecycle Events (.jsonl)"]
        ResponseValidator --> Scorer["Statistical Scorer (Wilson / Bootstrap / PRF)"]
    end

    subgraph Observability["User Interfaces & Observability"]
        Ledger --> TUI["Rich Terminal UI Dashboard"]
        Ledger --> WebUI["FastAPI Backend & React Frontend"]
        EventTail --> TUI
        EventTail --> WebUI
        EventTail --> Exporter["Redacted Trace Exporter (JSONL/CSV/ZIP)"]
    end
```

---

## 2. Core Architectural Principles

1. **Any Target with Input and Output**: Benchmarks raw completions, multi-turn dialogues, agent tools, or complex webhook pipelines using a uniform `Target` and `TargetResult` contract.
2. **Zero Simulation**: There is no mock data or dry-run mode in production. Missing provider telemetry (tokens, latency, confidence) remains `null` / `UNAVAILABLE`.
3. **Strict Ground-Truth Integrity**: Supervised quality metrics (accuracy, F1, calibration) are computed exclusively from human-approved annotations. Model agreement is never presented as accuracy.
4. **Fail-Closed Spend Protection**: Hard limits ($18 total, $2 pilot, $0.50 single run, $0.02 single case) checked preflight and at runtime. Unresolved costs lock execution until reconciled.
5. **Interactive Plan Approval**: Live network requests require explicit human confirmation typing the plan fingerprint in an interactive terminal.
6. **Local-First & Data Privacy**: All telemetry, run history, and databases reside locally. Sensitive fields are redacted and pseudonyms use salted SHA-256 hashes.

---

## 3. Subsystem Breakdown

### 3.1 Connectors & Workflow Targets (`runport.connectors`)
- **HTTP Transport**: Bounded-retry poster handling transient 408/429/5xx status codes and honoring `Retry-After`.
- **OpenRouter & OpenAI Compat**: Unified streaming and non-streaming completion adapters.
- **Dify Connector**: Chat completions and Server-Sent Events (SSE) streaming with secret scrubbing.
- **Workflow Connectors**: Flowise, Langflow, n8n, LangGraph, and custom HTTP JSON connectors.

### 3.2 Spend & Budget Engine (`runport.core.budget`)
- **Append-Only WAL Ledger**: SQLite database tracking micro-dollar costs by kind (`ACTUAL`, `ESTIMATED`, `UNRESOLVED`).
- **Circuit Breakers**: Immediate halt if a single evaluation case exceeds configured bounds.
- **Reconciliation Engine**: CLI and API mechanisms to resolve unpriced calls before resuming execution.

### 3.3 Statistical Scoring Subsystem (`runport.scorers`)
- **Binomial CIs**: Wilson score intervals for proportion metrics.
- **Bootstrap CIs**: Non-parametric percentile bootstrap confidence intervals.
- **Agreement**: Cohen's Kappa for inter-annotator reliability.
- **Multiple Comparisons**: Holm-Bonferroni step-down correction for family-wise error rates.

### 3.4 Presentation Layer
- **Rich Terminal UI (TUI)**: Full-screen dashboard, real-time telemetry graphs, candidate comparison roster, and trace inspector.
- **Developer Launcher**: Arrow-key workflow menu for fast navigation.
- **FastAPI & React Web Interface**: Localhost web application providing visual experiment planning, execution monitoring, and comparative reporting.

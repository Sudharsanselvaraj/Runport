# Runport Architecture & Design Decisions

This document records confirmed design and architectural decisions for **Runport** (`runport`), an open-source, local-first LLM, prompt, and workflow benchmarking platform.

---

## 1. Product Identity & Scope

* **Product Name**: Runport
* **Package / CLI**: `runport`
* **Repository**: `https://github.com/Sudharsanselvaraj/runport`
* **License**: Apache 2.0
* **Scope**: Universal benchmarking platform for any LLM API, prompt template, or orchestrated workflow (Dify, Flowise, n8n, Langflow, LangGraph, custom HTTP endpoints, Python callables).
* **Telemetry**: Zero external telemetry. All metrics, traces, and spend ledgers remain strictly local.

---

## 2. Spend Governance & Budget Policies

* **Fail-Closed Spend Caps**: Budget tracking is enforced locally via an append-only SQLite WAL ledger.
* **Workspace Defaults**:
  * Total Lifetime Ceiling: `$5.00` USD
  * Per-Run Ceiling: `$1.00` USD
  * Per-Case Ceiling: `$0.05` USD
  * Pilot Ceiling: `$1.00` USD
  * `require_priced`: `false` (unpriced models require an explicit `per_case_usd` cap)
  * Retry Buffer: `5%`
* **Fixed Provenance Vocabulary**:
  * `ACTUAL`: Exact provider-reported USD spend.
  * `ESTIMATED`: Verified catalog rate × reported tokens.
  * `UNRESOLVED`: Billed request with unknown cost.
  * `UNAVAILABLE`: Zero-cost unpriced / local execution.
  * `REPLAYED`: Offline replay execution ($0.00 spend).
* **Unresolved Spend Invariant**: Any unresolved ledger entry immediately blocks live runs fail-closed until operator reconciliation via `runport budget reconcile`.

---

## 3. Execution Plan & Approval Model

* **Cryptographic Plan Fingerprint**: Every execution plan generates an immutable SHA-256 fingerprint binding candidate models, endpoint routes, dataset hash, prompt template hash, and budget caps.
* **Recomputation Invariant**: The execution plan is freshly recomputed from disk immediately prior to authorization. Stale, modified, or mismatched fingerprints are rejected fail-closed.
* **Approval Mechanisms**:
  * **Interactive Terminal / TUI**: Operator types a confirmation phrase naming the plan fingerprint and ceiling.
  * **Web Dashboard**: Explicit modal dialog displaying projected spend and fingerprint before dispatch.
  * **CI / Non-Interactive**: Token-based approval via `--approve <plan_fingerprint>` (disabled by default in workspace config). Single-use tokens cannot be replayed.

---

## 4. Ground Truth & Evaluation Integrity

* **Agreement is Not Correctness**: Model-to-model consensus is never presented as accuracy. Supervised metrics require human ground-truth annotations.
* **No Tuning on Held-Out Splits**: Decision thresholds and hyper-parameters are calibrated on DEV splits only, frozen, and evaluated unchanged on TEST.
* **Dataset Immutability**: Source datasets are SHA-256 hashed before and after evaluation to guarantee immutability.
* **Missing Telemetry**: Null is never 0. Missing tokens, latency, confidence, or cost remain `None` / `UNAVAILABLE`.

---

## 5. Web Interface Architecture

* **Backend**: FastAPI REST service binding strictly to `127.0.0.1:8000` by default. Live events streamed via Server-Sent Events (SSE).
* **Frontend**: React + TypeScript + Vite + Tailwind CSS SPA, pre-built and bundled into `src/runport/_web` assets.
* **Security**: Single-user localhost execution. When bound to non-localhost interfaces (e.g. inside a container), `RUNPORT_API_TOKEN` is mandatory.

---

## 6. Target Connectors

* **Stable Candidates (Contract-Verified)**: `openai_compat`, `openrouter`, `dify`, `http_workflow`, `python_target`, `ollama`.
* **Experimental**: `flowise`, `langflow`, `n8n`, `langgraph` (labeled experimental until passing the contract test suite).

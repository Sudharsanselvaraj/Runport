# Runport Documentation

Welcome to the documentation for **Runport**, the universal, local-first open-source LLM, prompt, and workflow evaluation platform.

---

## 🧭 Documentation Map

| Section | Description | Link |
|:---|:---|:---:|
| **Quickstart Guide** | 2-minute walkthrough from installation to first live run. | [Read Guide](quickstart.md) |
| **Core Concepts & Invariants** | The 10 non-negotiable architectural invariants of Runport. | [Read Concepts](concepts.md) |
| **Metrics & Formulas** | Complete mathematical reference for accuracy, Wilson score CIs, bootstrap, and Cohen's $\kappa$. | [Read Metrics](metrics.md) |
| **Connectors & Integrations** | Setup guides for OpenRouter, OpenAI, Ollama, Dify, Flowise, n8n, LangGraph, and custom targets. | [Read Connectors](connectors.md) |
| **Safety & Spend Governance** | Append-only SQLite WAL ledger, fail-closed spend caps, SSRF protection, and PII redaction. | [Read Safety](safety.md) |
| **System Architecture** | Decoupled 5-layer design, storage engine, and execution lifecycles. | [Read Architecture](ARCHITECTURE.md) |
| **Product Readiness Audit** | Evidence-backed audit against latest main and milestone execution plan. | [Read Audit](GLOBAL_PRODUCT_READINESS_AUDIT.md) |
| **Configuration Reference** | Full schema specification for `runport.yaml` workspace settings. | [Read Config](config-reference.md) |
| **CLI Reference** | Complete command-line manual, subcommands, and flags. | [Read CLI Manual](cli.md) |
| **Web UI & Terminal Dashboard** | Dual interface guide: Rich fullscreen TUI and FastAPI + React local dashboard. | [Read UI Guide](web-ui.md) |
| **FAQ & Troubleshooting** | Frequently asked questions and common error resolutions. | [Read FAQ](faq.md) |

---

## 🌟 Core Principles

1. **Null is Not 0**: Missing tokens, latency, confidence, or cost remain `None` / `UNAVAILABLE`. Never fabricate or default missing telemetry to zero.
2. **Fixed Provenance Vocabulary**: Spend is classified strictly as `ACTUAL`, `ESTIMATED`, `UNRESOLVED`, `UNAVAILABLE`, or `REPLAYED`.
3. **Strict Runner Guard Order**: Execution always proceeds through 7 explicit gates in order:
   $$\text{Auth Check} \longrightarrow \text{Privacy Gate} \longrightarrow \text{Preflight Budget} \longrightarrow \text{Transport} \longrightarrow \text{Validation} \longrightarrow \text{Persistence} \longrightarrow \text{Spend Booking}$$
4. **Unresolved Spend Blocks Execution**: Requests with unknown costs are recorded as `UNRESOLVED` and block subsequent live runs fail-closed until operator reconciliation (`runport budget reconcile`).
5. **Cryptographic Plan Fingerprint**: Execution plan fingerprint SHA-256 binds candidate models, endpoint routes, dataset hash, prompt template hash, and budget caps. Mismatched or stale approvals are rejected.
6. **Immutable Sources**: Source datasets are hashed (SHA-256) before and after evaluation to guarantee immutability.
7. **Zero Leakage & Secret Scrubbing**: API keys, bearer tokens, and secrets are automatically scrubbed from request logs, trace events, and exports.
8. **Agreement is Not Correctness**: Model-to-model consensus (e.g. Cohen's Kappa) is never presented as accuracy. Supervised metrics strictly require human ground-truth approval.
9. **No Tuning on Held-Out Splits**: Decision thresholds and hyper-parameters are calibrated on DEV only, frozen, and evaluated unchanged on TEST.
10. **Zero Simulation in Core Modules**: Test doubles exist only under `tests/`. Replay executions are isolated, carry provenance `REPLAYED`, and book `$0.00` spend.


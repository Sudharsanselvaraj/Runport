# Core Concepts & Architectural Invariants

Runport is built on non-negotiable architectural principles that prioritize financial safety, scientific validity, and data privacy.

---

## The 10 Invariants

1. **Null is not 0**: Missing tokens, latency, confidence, or cost remain `None` / `UNAVAILABLE`. Never fabricate or default missing telemetry to zero.
2. **Fixed Provenance Vocabulary**: All cost accounting strictly uses:
   - `ACTUAL`: Exact provider-reported USD spend from billing response.
   - `ESTIMATED`: Verified catalog rate × reported token counts.
   - `UNRESOLVED`: Billed request with unknown cost.
   - `UNAVAILABLE`: Zero-cost unpriced / local execution ($0.00).
3. **Strict Runner Guard Order**:
   Execution always proceeds through 7 explicit gates in order:
   $$\text{Auth Check} \longrightarrow \text{Privacy Gate} \longrightarrow \text{Preflight Budget \& Context} \longrightarrow \text{Transport} \longrightarrow \text{Validation} \longrightarrow \text{Persistence} \longrightarrow \text{Spend Booking}$$
4. **Unresolved Spend Blocks Execution**: Any request that generates unknown cost books as `UNRESOLVED` ($0.00 spend initially) and immediately halts subsequent live runs fail-closed until an operator reconciles it via `runport budget reconcile`.
5. **Cryptographic Plan Fingerprint**: Every execution plan generates an immutable SHA-256 fingerprint binding candidate models, endpoint routes, dataset hash, prompt template hash, and budget caps. Mismatched or stale approvals are rejected.
6. **Immutable Sources**: Source datasets are hashed (SHA-256) before and after evaluation to guarantee immutability.
7. **Zero Leakage & Secret Scrubbing**: API keys, bearer tokens, passwords, and sensitive identifiers are automatically scrubbed from request logs, trace events, and exports.
8. **Agreement is Not Correctness**: Model-to-model consensus or majority voting is never presented as accuracy. Supervised metrics strictly require human-approved ground-truth annotations.
9. **No Tuning on Held-Out Splits**: Decision thresholds and hyper-parameters are calibrated on DEV splits only, frozen, and evaluated unchanged on TEST.
10. **Zero Simulation in Core Modules**: Test doubles exist only under `tests/`. Core modules never simulate provider responses or fabricate judgments. Replay executions are isolated, carry provenance `REPLAYED`, and book `$0.00` spend.

---

## Fail-Closed Spend Caps

LLM benchmarking can quickly incur runaway costs if loops run unchecked or unpriced token streams are processed.

Runport enforces hard financial safety via an append-only SQLite WAL ledger (`runport.db`):
- **Total Budget Ceiling**: Hard limit across the entire workspace lifecycle (e.g. `$5.00`).
- **Pilot Spend Ceiling**: Maximum spend allowed for a single evaluation pilot (e.g. `$1.00`).
- **Per-Run Ceiling**: Maximum spend per single command run (e.g. `$1.00`).
- **Per-Case Ceiling**: Maximum spend per single test case (e.g. `$0.05`).

If a projected request would exceed any ceiling, the preflight guard aborts execution before the socket opens.

---

## Cryptographic Plan Fingerprint

Before any live evaluation run begins, Runport compiles an `ExecutionPlan`. The plan computes a cryptographic SHA-256 hash across:
- Evaluator version and options
- Target endpoints and model identifiers
- Canonical SHA-256 hash of the input dataset
- Canonical SHA-256 hash of prompt templates
- Current budget caps

In interactive sessions, the user reviews this plan and types `APPROVE` or confirms the exact fingerprint. If the dataset or prompt is modified after approval, the fingerprint changes and execution is rejected.

---

## Supervised Truth vs. Consensus

In production evaluations, many tools rely on "LLM-as-a-judge" or multi-model agreement as a proxy for accuracy. Runport explicitly rejects this pattern:
- **Consensus ($\kappa$, agreement rates)** measures consistency between models, not correctness.
- **Accuracy, Precision, Recall, and F1** are computed strictly against human-verified annotations (`ground_truth`).
- When ground truth is absent, outputs are evaluated for structural validity, latency, and cost — but never labeled as "accurate".

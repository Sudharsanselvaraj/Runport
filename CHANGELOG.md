# Changelog

All notable changes to Runport are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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

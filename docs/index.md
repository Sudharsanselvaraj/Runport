# Runport

**Universal, local-first open-source LLM, prompt, and workflow benchmarking platform under hard spend caps.**

---

[![CI](https://github.com/Sudharsanselvaraj/runport/actions/workflows/ci.yml/badge.svg)](https://github.com/Sudharsanselvaraj/runport/actions/workflows/ci.yml)
[![Python 3.11 | 3.12 | 3.13](https://img.shields.io/badge/python-3.11%20%7C%203.12%20%7C%203.13-blue.svg)](https://github.com/Sudharsanselvaraj/runport)
[![License: Apache-2.0](https://img.shields.io/badge/license-Apache--2.0-green.svg)](https://github.com/Sudharsanselvaraj/runport/blob/main/LICENSE)
[![Status: Public Alpha](https://img.shields.io/badge/status-public--alpha-orange.svg)](https://github.com/Sudharsanselvaraj/runport)

Runport benchmarks any AI target — raw LLM endpoints, prompt variations, RAG pipelines, or orchestrated workflow graphs (such as Dify, Flowise, Langflow, n8n, and custom Python callables) — while enforcing fail-closed budget caps and strict ground truth evaluation.

---

## Key Highlights

- **Universal Evaluation Targets**: Benchmark direct API endpoints, multi-step agent graphs, retrieval pipelines, or local Python functions through a unified abstraction.
- **Fail-Closed Spend Protection**: Every dollar is tracked in an append-only SQLite WAL ledger. If spend reaches the hard cap or an unpriced request occurs, execution halts immediately.
- **Cryptographic Plan Fingerprinting**: Every execution plan generates an immutable SHA-256 fingerprint binding target routes, dataset hashes, prompt versions, and spend limits.
- **Strict Ground Truth**: Supervised metrics (accuracy, F1, calibration) are computed exclusively from human-verified annotations. Model-to-model consensus is never presented as accuracy.
- **Zero Telemetry & Local-First**: Runport runs 100% locally. Zero telemetry, zero external pings, and automatic scrubbing of bearer tokens, API keys, and sensitive data.
- **Multi-Modal Visibility**: Interactive terminal UI (Rich), modern web dashboard (FastAPI + React), and sanitized trace exports.

---

## Quick Navigation

- [Quickstart Guide](quickstart.md): Install and run your first benchmark in 60 seconds.
- [Core Concepts & Invariants](concepts.md): Learn the 10 immutable invariants of Runport.
- [Configuration Reference](config-reference.md): Full schema of workspace and runner settings.
- [Connectors & Targets](connectors.md): Target adapters for Dify, Flowise, Langflow, n8n, and custom HTTP/Python.
- [Statistical Metrics](metrics.md): Mathematical definitions of accuracy, Wilson score intervals, and calibration.
- [Safety & Privacy](safety.md): Data isolation, preflight checks, and secret scrubbing.
- [Web & Terminal UI](web-ui.md): Explore the local dashboard and real-time terminal views.
- [CLI Reference](cli.md): Complete list of commands and flags.
- [FAQ](faq.md): Frequently asked questions.

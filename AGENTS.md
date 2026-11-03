# AGENTS.md — Runport

Guide for AI coding agents and developers working in this repository. Read it fully before making any changes. It details the project architecture, non-negotiable invariants, test procedures, and commit rules.

---

## 1. Project Overview

**Runport**: A universal, local-first open-source LLM, prompt, and workflow benchmarking platform that:

1. Benchmarks **any API or orchestrated workflow** (raw LLMs, prompt wrappers, autonomous agents, Dify, Flowise, Langflow, n8n, LangGraph, custom HTTP endpoints);
2. Enforces **strict ground truth**: supervised metrics (accuracy, F1, calibration) are computed exclusively from human-approved annotations;
3. Accounts for spend under hard, fail-closed spend caps via an append-only SQLite WAL ledger;
4. Delivers visibility through a read-only terminal UI (Rich), a modern local web dashboard (FastAPI + React), and sanitized trace exports.

**Tech Stack**: Python 3.11+, `uv`, Typer (CLI), FastAPI (Web Backend), React + Vite + TypeScript (Web Frontend), Rich (TUI), Pydantic v2, SQLite (WAL mode), pytest.

---

## 2. Architectural Invariants (Never Weaken)

1. **Null is not 0**: Missing tokens, latency, confidence, or cost remain `None` / `UNAVAILABLE`. Never fabricate or default missing telemetry to zero.
2. **Fixed Provenance Vocabulary**: All cost accounting strictly uses:
   - `ACTUAL`: Exact provider-reported USD spend.
   - `ESTIMATED`: Verified catalog rate × reported tokens.
   - `UNRESOLVED`: Billed request with unknown cost.
   - `UNAVAILABLE`: Zero-cost unpriced / local execution.
3. **Strict Runner Guard Order**:
   `Authorization Check` → `Privacy Gate` → `Preflight Budget & Context Check` → `Transport Execution` → `Strict Validation` → `Persistence` → `Spend Booking` (booked as `UNRESOLVED` if cost is unavailable).
4. **Unresolved Spend Blocks Execution**: Unresolved ledger entries block further live runs fail-closed until reconciled via `runport budget reconcile`.
5. **Cryptographic Plan Fingerprint**: Execution plan fingerprint SHA-256 binds candidate models, endpoint routes, dataset hash, prompt template hash, and budget caps. Mismatched or stale approvals are rejected.
6. **Immutable Sources**: Source datasets are hashed (SHA-256) before and after evaluation to guarantee immutability.
7. **Zero Leakage & Secret Scrubbing**: API keys, bearer tokens, and secrets are automatically scrubbed from request logs, trace events, and exports.
8. **Agreement is Not Correctness**: Model-to-model consensus is never presented as accuracy. Supervised metrics require human ground-truth approval.
9. **No Tuning on Held-Out Splits**: Decision thresholds and hyper-parameters are calibrated on DEV only, frozen, and evaluated unchanged on TEST.
10. **Zero Simulation in Core Modules**: Test doubles exist only under `tests/`. Replay executions are isolated, carry provenance `REPLAYED`, and book `$0.00` spend.

---

## 3. Git & Workflow Rules

- **Git Identity**: `Sudharsanselvaraj`.
- **No AI Attribution**: No "Co-authored-by: Claude", no "Generated with Claude", and no AI assistant trailers in commit messages or pull requests.
- **Commit Granularity**: One logical change per commit with a concise, descriptive imperative message.
- **Never Commit Secrets or Runtime Artifacts**: Never commit `.env*`, `*.db`, `*.db-wal`, `data/budget_policy.json`, `reports/`, or private datasets.
- **Safety**: Never force-push (`git push --force`).

---

## 4. Repository Layout

```text
.
├── AGENTS.md                     # Developer and agent guidance (this file)
├── README.md                     # Public project overview, quickstart, architecture
├── LICENSE / NOTICE              # Apache 2.0 license and attribution
├── pyproject.toml / uv.lock      # Python project configuration and lockfile
├── assets/                       # Visual assets, logos, and UI SVG recordings
├── docs/                         # Technical design and architecture documentation
├── src/runport/                  # Core package
│   ├── api/                      # FastAPI REST routes and web service
│   ├── catalog/                  # Model metadata and catalog registries
│   ├── classification/           # Classification benchmark runner and metrics
│   ├── cli.py                    # Typer CLI entry points
│   ├── connectors/               # Workflow and API adapters (Dify, Flowise, n8n, etc.)
│   ├── core/                     # Configuration, BudgetService, and LiveGuard
│   ├── datasets/                 # Ingestion, sanitization, and redaction
│   ├── observability/            # Telemetry, EventTail, and trace export
│   ├── providers/                # HTTP transport with bounded retries and OpenRouter adapter
│   ├── runs/                     # Execution engine and ReplayRunner
│   ├── scorers/                  # Statistical metrics (Wilson CI, Bootstrap, Kappa)
│   ├── storage/                  # SQLite WAL database and ledger manager
│   ├── targets/                  # Unified Target and TargetResult abstractions
│   └── tui/                      # Rich terminal user interface
├── web/                          # React + TypeScript + Vite web dashboard
├── examples/plugins/             # Decoupled plugin reference implementations
├── tests/                        # Offline test suite (sockets blocked)
└── data/                         # Local evaluation fixtures
```

---

## 5. Testing & Verification

All automated tests run completely offline with fake transports and blocked sockets.

```bash
# Sync dependencies
uv sync --extra dev --extra report

# Run complete core test suite
uv run pytest

# Run plugin test suite
uv run pytest examples/plugins

# Run specific module tests
uv run pytest tests/test_connectors.py
uv run pytest tests/test_web_api.py
```

---

## 6. Common Commands

```bash
uv run runport                         # Interactive launcher
uv run runport web                     # Launch web dashboard at http://127.0.0.1:8000
uv run runport ui                      # Terminal UI dashboard
uv run runport api-preflight           # Offline API credential verification
uv run runport budget status           # Ledger status and remaining caps
uv run runport validate-dataset        # Dataset schema and leakage validation
uv run runport export-traces -f zip    # Export sanitized local trace records
```

# AGENTS.md — Runport

Guide for AI coding agents (and humans) working in this repository. Read it fully before changing anything. It describes what the project is, how the packages fit together, the rules that must never be broken, and how to verify your work.

## 1. What this project is

**Runport**: A universal, local-first open-source LLM, prompt, and workflow benchmarking platform that:

1. Benchmarks **any API or orchestrated workflow** (raw LLMs, prompts, agents, Dify, Flowise, Langflow, n8n, LangGraph, custom HTTP endpoints);
2. Enforces **strict ground truth**: supervised metrics (accuracy, F1, calibration) are computed exclusively from human-approved annotations;
3. Accounts for spend under hard, fail-closed spend caps via an append-only SQLite WAL ledger;
4. Observes execution via a read-only terminal dashboard (TUI) and exports sanitized local trace records.

Python 3.11+, `uv`, Typer (CLI), Rich (TUI), Pydantic v2, SQLite (WAL), pytest.

## 2. Non-negotiable rules

Break none of these. If a task seems to require it, stop and ask the user.

1. **No simulation, no mock data, no fabricated values.** There is no dry-run mode in production modules. Missing tokens, latency, confidence, cost or telemetry stay `null`/`UNAVAILABLE`. A prediction is never ground truth. Never create placeholder trace rows for models that did not run.
2. **No network call without explicit user approval of an exact plan.** Live requests need an interactive, typed approval phrase that includes the plan fingerprint (`core/live_guard.py`). Never call a model API, spend credits, configure or print an API key, or transmit confidential data while implementing or testing. Tests run offline (fake transports; sockets blocked).
3. **Confidential data stays local unless the operator authorizes a specific benchmark.** Real confidential records pass only through authorized flows requiring typed confirmation bound to plan fingerprints and dataset versions.
4. **Secrets never enter the repo, logs, events or exports.** The API key comes only from the user's environment (`OPENROUTER_API_KEY`). Never ask for it in chat.
5. **Budget guards stay effective.** Default caps: $18 total, $2 pilot, $0.50 per run, $0.02 per case. Unresolved-spend entries block live runs until reconciled. Spend kinds stay separate: ACTUAL (provider-reported), ESTIMATED (catalogue price × reported tokens), UNRESOLVED.
6. **Ground truth only after human approval.** Supervised metrics are computed only from approved labels. Otherwise show `GROUND TRUTH PENDING`.
7. **Never tune on the held-out split.** Thresholds are chosen on DEV only, frozen, then applied unchanged to TEST.
8. **Agreement is not correctness.** Never present model–model agreement as accuracy.
9. **Source data is read-only.** Source datasets and prediction stores are never modified by dashboards or exports.
10. **Be honest in reports.** State exactly what was run and what failed. Say what you did not verify.

## 3. Git and workflow conventions

- Configured git identity: `Sudharsanselvaraj`.
- **No Claude co-author line, no "Generated with Claude" trailer, no attribution** in commits or PRs.
- Never commit git-ignored or confidential files. Never force-push.
- Preserve uncommitted work and unrelated functionality.
- Keep the visual identity of the TUI (dark slate/navy background, muted purple selection, restrained accents). No emojis in UI text.

## 4. Repository map

```text
.
├── AGENTS.md                     # this file
├── README.md                     # user-facing overview, commands, safety model
├── LICENSE                       # Apache 2.0
├── NOTICE                        # Apache 2.0 attribution notice
├── pyproject.toml / uv.lock      # dependencies and project metadata
├── assets/                       # project assets and screenshots
├── docs/                         # design and migration documents
├── src/runport/                  # Runport core package (section 5)
├── examples/plugins/             # decoupled plugins (KB audit, Jev Decisions API)
├── tests/                        # offline test suite (section 8)
└── data/                         # local evaluation fixtures (git-ignored runtime DBs/telemetry)
```

### 5. Package layout (`src/runport/`)

| Folder / file | Responsibility | Key facts |
|---|---|---|
| `cli.py` | Typer entry point and launcher loop | Commands: `smoke-test`, `api-preflight`, `models roster/list`, `budget status/reconcile`, `validate-dataset`, `export-traces`, `ui`, etc. Bare `runport` opens launcher. |
| `catalog/` | Model participant catalog | `ModelCandidate` schema and portfolio definitions. |
| `connectors/` | External workflow integrations | `dify.py` (chat and streaming SSE poster with secret scrubbing). |
| `scorers/` | Statistical scoring utilities | `stats.py` (Wilson CI, bootstrap CI, Cohen's Kappa, PRF, Holm correction). |
| `datasets/` | Dataset sanitization and ingestion | `redaction.py` (PII redaction and salted hash pseudonyms). |
| `core/` | Configuration and spend guards | `config.py` (settings, paths), `budget.py` (`BudgetService`), `live_guard.py` (typed confirmation). |
| `storage/db.py` | SQLite WAL ledger + evaluation tables | Ledger columns `is_simulated`, `is_unresolved`, `cost_basis`. |
| `providers/` | Provider adapters and HTTP transport | `base.py`, `http.py` (bounded retries), `openrouter.py`. |
| `classification/` | Classification benchmarking stack | Contracts, validators, lead summary, splits, metrics, runner, smoke test. |
| `observability/` | Telemetry and export | `events.py` (request events), `aggregate.py`, `analysis.py`, `monitor.py` (`LiveMonitor`), `export.py`. |
| `tui/` | Rich terminal UI | `app.py`, `screens.py`, `live_views.py`, `telemetry.py`, `theme.py`, `health.py`. |
| `traces/` | Trace ingestion and analysis | Redacted Langfuse import and diagnostic classifier. |

## 6. Testing

```bash
uv sync
uv run pytest                      # full main test suite
uv run pytest examples/plugins     # plugin test suite
```

Rules for tests:
- Synthetic, hand-written fixtures only. Test doubles live under `tests/`; nothing in `src/` may simulate a provider.
- Sockets blocked; fake transport for offline tests.
- Add or update tests with every behavior change. Report real pass/fail numbers; never claim a run you did not make.

## 7. Common commands

```bash
uv run runport                         # launcher
uv run runport ui                      # full-screen dashboard
uv run runport models roster           # comparison roster and blockers
uv run runport api-preflight           # check key availability offline
uv run runport budget status           # spend ledger and remaining caps
uv run runport export-traces -f zip    # redacted trace export
```

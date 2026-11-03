# Project Map: Runport (`runport`)

**Status**: Phase 0 Complete; Core Architecture & Test Baselines Established  
**License**: Apache 2.0  
**Repository**: `https://github.com/Sudharsanselvaraj/Runport.git`

---

## 1. Confirmed Repository State

### 1.1 Python & Tooling Environment
- **Runtime**: Python 3.11+ (tested on Python 3.11.7 and 3.12)
- **Package Manager**: `uv` (fast, reproducible virtualenv and lockfile resolution)
- **CLI Framework**: Typer
- **TUI Framework**: Rich (terminal dashboard and developer launcher)
- **Persistence**: SQLite in WAL mode (append-only ledger)
- **Test Suite**: `pytest` (684 passing tests offline)

### 1.2 Configuration & Spend Invariants
- Default experiment cap: `$18.00` total, `$2.00` pilot, `$0.50` max single run, `$0.02` max single case.
- `RUNPORT_SKIP_DOTENV=1` supported for isolated test execution.
- Secrets read strictly from environment (`OPENROUTER_API_KEY`).
- Invariant: Zero simulation in production modules. No mock responses or fabricated costs.

---

## 2. Repository Layout

```text
runport/
├── pyproject.toml              # Project metadata, dependencies, entry points
├── uv.lock                     # Deterministic dependency lockfile
├── README.md                   # Public documentation, quickstart, architecture
├── LICENSE                     # Apache 2.0 License
├── NOTICE                      # Copyright notice
├── AGENTS.md                   # Agent engineering guidelines & safety rules
├── .gitignore                  # Targeted, precision ignore rules
│
├── assets/                     # Logos and documentation visual assets
│   ├── Runport Hexagonal Logo.png
│   ├── Runport Geometric Emblem Logo.png
│   └── readme/                 # Terminal UI screenshots and SVG recordings
│
├── docs/                       # Design, migration, and specification docs
│   ├── ARCHITECTURE.md         # System architecture and data flow
│   ├── CURRENT_ARCHITECTURE.md # Current implementation design
│   ├── GAP_ANALYSIS.md         # Specification gap analysis vs BUILD PROMPT
│   ├── MIGRATION_LOG.md        # Migration history and phase checkpoints
│   ├── OPEN_DECISIONS.md       # Owner decisions log
│   └── PROJECT_MAP.md          # This file
│
├── src/runport/                # Core platform package
│   ├── __init__.py             # Public version and package exports
│   ├── cli.py                  # CLI command entry point and launcher
│   ├── catalog/                # Participant portfolio and model specifications
│   │   ├── __init__.py
│   │   └── models.py           # ModelCandidate schema
│   ├── connectors/             # Workflow and API connectors
│   │   ├── __init__.py
│   │   └── dify.py             # Dify chat and SSE streaming connector
│   ├── scorers/                # Statistical evaluation metrics
│   │   ├── __init__.py
│   │   └── stats.py            # Wilson CI, Bootstrap, Kappa, PRF, Holm
│   ├── datasets/               # Ingestion and privacy sanitization
│   │   ├── __init__.py
│   │   └── redaction.py        # Salted hash pseudonyms and PII regex redaction
│   ├── classification/         # Classification benchmarking stack
│   │   ├── contracts.py        # Case schemas and data contracts
│   │   ├── runner.py           # Execution engine with guard order
│   │   ├── validators.py       # Strict output format validators
│   │   ├── metrics.py          # Supervised classification and binary metrics
│   │   ├── realdata.py         # Operator authorization and atomic run records
│   │   └── smoke.py            # Synthetic offline smoke test runner
│   ├── core/                   # Configuration and spend protection
│   │   ├── config.py           # App settings and environment resolution
│   │   ├── budget.py           # Fail-closed BudgetService and ledger guards
│   │   ├── budget_policy.py    # Policy rules and spend limits
│   │   └── live_guard.py       # Typed fingerprint approval guard
│   ├── storage/                # Database engine
│   │   ├── __init__.py
│   │   └── db.py               # SQLite WAL ledger and run history
│   ├── providers/              # HTTP transports and adapters
│   │   ├── base.py             # Transport interfaces and secret scrubber
│   │   ├── http.py             # Bounded-retry HTTP poster
│   │   └── openrouter.py       # OpenRouter chat completions adapter
│   ├── observability/          # Telemetry and reporting
│   │   ├── events.py           # Request lifecycle event logger
│   │   ├── aggregate.py        # Metrics aggregations and percentiles
│   │   ├── analysis.py         # Quality, calibration, and agreement metrics
│   │   ├── monitor.py          # Real-time state polling monitor
│   │   └── export.py           # Redacted trace exporter (JSONL, CSV, ZIP)
│   └── tui/                    # Terminal dashboard interface
│       ├── app.py              # WorkbenchTUI application
│       ├── screens.py          # Dashboard screen layouts
│       ├── live_views.py       # Reactive view components
│       ├── telemetry.py        # System resource sampling
│       ├── theme.py            # Theme definitions
│       └── welcome.py          # Workflow selection menu
│
├── examples/plugins/           # Reference plugins and domain integrations
│   ├── kb_audit/               # Markdown knowledge-base audit engine
│   └── jev_decisions_api/      # Decisions API payload builder
│
├── tests/                      # Offline test suite (sockets blocked)
└── data/                       # Local evaluation datasets and test fixtures
```

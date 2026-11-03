# Web Dashboard & Terminal UI

Runport provides dual observation interfaces: a developer-grade Terminal User Interface (TUI) powered by Rich, and a modern local Web Dashboard powered by FastAPI and React.

---

## 1. Terminal UI (TUI)

Launch the full-screen terminal interface:

```bash
uv run runport ui
```

### Features
- **Real-Time Telemetry Monitor**: Displays active spend, remaining budget caps, model readiness, and error rates.
- **Model Roster**: Interactive inspection of configured models, pricing rates, route status, and latency stats.
- **Fail-Closed Budget Guard**: Visual indicators of spend balances, warning when approaching per-run or total caps.
- **Offline / Dark Theme**: Designed specifically for terminal contrast and standard UTF-8/Braille rendering.

---

## 2. Local Web Dashboard

Start the local web server:

```bash
uv run runport web
```

By default, the server listens at `http://127.0.0.1:8000`.

### Key Pages & Capabilities
- **Overview & Runs**: Explore past benchmark runs, compare candidate model accuracy side by side, and inspect Wilson score intervals.
- **Model Comparison Table**: Compare latency percentiles (p50, p90, p95), output validity rates, and cost per 1,000 requests.
- **Budget & Ledger**: Full visibility into the append-only SQLite WAL ledger, itemizing every transaction by timestamp, model, tokens, and provenance.
- **Trace Inspector**: Drill down into individual prompt/response pairs with automated redaction of sensitive tokens.

---

## 3. Sanitized Trace Exports

Export benchmark traces for offline analysis, archiving, or sharing:

```bash
# Export traces as a structured zip archive
uv run runport export-traces -f zip --out-dir reports/exports

# Export traces as JSONL
uv run runport export-traces -f jsonl --out-dir reports/exports
```

Export features:
- Automatically sanitizes API tokens and forbidden fields before saving.
- Generates a cryptographically hashed manifest.
- Never overwrites existing export files.

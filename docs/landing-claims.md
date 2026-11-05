# Landing page claims

Every claim, number and label in the bento feature section ("What Runport does") and the product
window ("Workbench"), with the file or test that backs it. Sample figures are marked as such on the
page and come only from `web/src/data/sampleRun.ts`.

## Claims about Runport

| Claim on the page | Where | Source |
| --- | --- | --- |
| One interface for models, prompts and workflows | Targets card | `src/runport/targets/` (Target, TargetResult); every connector in `src/runport/connectors/` returns a TargetResult |
| "6 supported · 4 experimental" (caption under the orbit) | Targets card | Computed from `web/src/data/connectors.ts`, which mirrors the `docs/connectors/README.md` status table (6 Stable, 4 Experimental); `tests/test_landing_connectors.py`, `web/tests/frames.test.ts` |
| Supported / Experimental in each tile's tooltip | Targets card | Same table; the eight tiles are real connectors with their real status (`orbitTiles()` in `graphics/frames.ts`, tested) |
| Approval is bound to the exact plan; a changed plan's approval is rejected | Plan and approval card | AGENTS.md invariant 5; `tests/test_runs_engine.py` (fingerprint binding); the demo never shows Approved next to a changed fingerprint (`web/tests/frames.test.ts`) |
| The fingerprint binds models, routes, dataset, template and caps | Plan panel, product window | AGENTS.md invariant 5 |
| Ceilings are checked before every request (every live request; replay runs make none) | Spend guard card | Runner guard order (AGENTS.md invariant 3: preflight budget check comes before transport); `tests/test_classification.py::test_runner_strict_guard_order` |
| A request that would cross the cap is blocked before it is sent ("blocked before sent") | Spend guard card | `docs/faq.md` ("execution halts fail-closed before the network socket opens"); `tests/test_budget.py`, `tests/test_live_safety.py` |
| Per-run ceiling $1.00 | Spend guard ring, product window | `BudgetConfig.per_run_usd` default in `src/runport/core/workspace.py`; `web/tests/sampleRun.test.ts` |
| Total $5.00, per case $0.05 | Product window (Plan tab) | `BudgetConfig.total_usd` and `per_case_usd` defaults in `src/runport/core/workspace.py`; `web/tests/sampleRun.test.ts` |
| Scores come only from human-approved labels | Results card, product window | AGENTS.md invariant 8; `src/runport/scorers/stats.py` (`wilson`) |
| Agreement is reported as agreement, not accuracy | Results card, product window | AGENTS.md invariant 8; `src/runport/scorers/stats.py` (`cohen_kappa`) |
| Thresholds frozen on DEV | Product window (Results tab) | AGENTS.md invariant 9 |
| The seven runner guards, in order: Authorization, Privacy gate, Preflight budget, Transport, Validation, Persistence, Spend booking | Product window (Live Run tab) | AGENTS.md invariant 3; `src/runport/runs/executor.py`; `tests/test_runs_engine.py`, `tests/test_classification.py::test_runner_strict_guard_order` |
| `runport web` serves the dashboard on your machine at 127.0.0.1:8000 | Product window heading and address bar | `src/runport/cli/commands/ui.py` (`web_cmd`: host default 127.0.0.1, port default 8000) |
| Provenance labels ACTUAL, ESTIMATED, UNRESOLVED, UNAVAILABLE | Product window | `CostBasis` in `src/runport/targets/base.py` |
| ACTUAL-LOCAL for a local Ollama row | Product window | `docs/connectors/README.md` (Ollama cost accounting). The code records local cost as `CostBasis.UNAVAILABLE`; the page follows the documented label, which is a known docs/code difference |

## Sample data (labelled "Sample data" on the page)

All from `web/src/data/sampleRun.ts`. Derived values are computed by its helpers and checked by
`web/tests/sampleRun.test.ts` and `web/tests/frames.test.ts`.

| Figure | Value | How it is produced |
| --- | --- | --- |
| Plan | support-triage v3, TEST split, 240 cases | `PLAN` |
| Fingerprints in the approval demo (first 12 hex characters) | 9f2c41d07be3 → b71e09a45c1f | `PLAN_FINGERPRINTS` |
| Accuracy | 91.3% (219 / 240), Wilson 95% 87.0–94.2% | `RESULTS`, `wilson()` |
| p95 / p50 latency | 1.62 s / 402 ms | `RESULTS` |
| Cost per 1k cases | $0.0645, ESTIMATED | catalog rate × mean tokens (`costPer1kCell`) |
| Unresolved spend | — (1 entry, blocks live runs); shown in the product window only | `LEDGER`, `unresolvedCount`; the amount is unknown, so it renders as an em dash, never $0.00 |
| Confusion matrix and per-class recall | 5 classes, 240 cases, 219 on the diagonal; labels from one mapping (`CLASS_LABELS`: billing, tech, account, shipping, other) | `CONFUSION`; totals checked against the accuracy in `web/tests/frames.test.ts` |
| Agreement κ | 0.61 (gpt-4o-mini vs llama3.1:8b) | `AGREEMENT` |
| Spend guard requests | req-01 $0.55 and req-02 $0.45 booked ($1.00, the per-run cap); req-03 ($0.12) would cross it and is blocked before sent. The ring starts each loop at $0.00 because nothing is booked yet (a known zero, not a missing value) | `SPEND_STEPS`, `spendPlan()`; an unpriced request would show an em dash and not count (tested) |
| Live run | run-0412, 132 / 240 | `LIVE_RUN` |

## Labelling

The bento section carries one caption under the grid: "Illustrations use sample data." The product window keeps its own "Sample data" chip.

## Not claimed

- No connector count is shown other than the 6 / 4 split from the registry table.
- No figure on these two sections renders an unknown or unresolved value as 0 or $0.00.

## Quality checks (2026-11-05, production build)

- Playwright layout test `web/tests/e2e/bento-layout.e2e.mjs`: passes at 1440, 1280, 1024, 768 and 390 px
  (no overlapping or clipped text, ring text inside the ring, equal top edges per row, no horizontal
  scroll, contrast at least 4.5:1); its self-check catches injected faults.
- axe (whole page): 0 violations at 1440, 1024, 768 and 390 px.
- Lighthouse mobile: Performance 96, Accessibility 100, Best Practices 100, SEO 100.
- Lighthouse desktop: 100, 100, 100, 100.
- Screenshots: `docs/landing_screenshots/before/` and `docs/landing_screenshots/after/` (section at five
  widths, card frames at 0, 3, 6 and 9 s), plus full pages in `docs/landing_screenshots/`.

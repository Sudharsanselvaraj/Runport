---
title: Budget guardrails
description: How the spend ceilings are checked, when a run is refused, and how unresolved spend is handled.
---

Runport tracks spend in an append-only SQLite ledger and refuses live requests that would cross a ceiling. These are local governance limits, not provider-enforced account limits; keep a limit at your provider as well.

## The ceilings

| Ceiling | Config field | Default |
|---|---|---|
| Total (lifetime) | `budget.total_usd` | $5.00 |
| Pilot | `budget.pilot_usd` | $1.00 |
| Per run | `budget.per_run_usd` | $1.00 |
| Per case | `budget.per_case_usd` | $0.05 |

## Preflight

Before a live request is sent, its projected cost must pass every check, in this order:

1. No `UNRESOLVED` entries exist in the ledger.
2. The projection does not exceed the per-run ceiling.
3. Spend so far plus the projection stays within the total ceiling.
4. Pilot spend so far plus the projection stays within the pilot ceiling.

How the projection is made:

| Runner | Projection |
|---|---|
| `GenericRunner`, priced target | Price of 1,000 input + 500 output tokens |
| `GenericRunner`, unpriced target | `per_case_usd` (must be positive), or refused if `require_priced: true` |
| `runport benchmark --live` | $0.0003 per case for the whole batch |

A failed check raises `BudgetExceededError`, and nothing is sent.

## Unresolved spend

When a billed request comes back without a usable cost, Runport cannot know what you were charged. It books the request as `UNRESOLVED` and blocks every further live run until you record the real amount:

```bash
uv run runport budget status
uv run runport budget reconcile --transaction-id TX --amount-usd 0.0042 --note "dashboard 2026-11-04"
```

## Changing ceilings

- Edit `runport.yaml` for the total, per-run and per-case ceilings.
- Use `runport budget raise-pilot-ceiling --to AMOUNT --operator NAME` to raise the pilot ceiling with a typed confirmation and an audit trail. It can never exceed the total ceiling.

`runport budget policy` shows the effective ceilings and the history of pilot changes. See [Budget commands](/cli-budget).

## What does not count

Replay runs and offline plans book nothing. Local execution (Ollama, Python targets) is booked at $0.00 as `UNAVAILABLE`.

---
title: Cost analysis
description: Cost provenance, the pricing formula, and how spend is booked and audited.
---

Every cost Runport records carries a provenance label, so a cheap-looking number is never confused with a missing one.

## Provenance

| Label | When | Amount |
|---|---|---|
| `ACTUAL` | The provider reported the cost, in verified USD | As reported |
| `ESTIMATED` | Tokens were reported and a verified price exists | Price × tokens |
| `UNRESOLVED` | A billed request returned no usable cost or token data | Unknown; blocks live runs |
| `UNAVAILABLE` | Local or unpriced execution | $0.00 |
| `REPLAYED` (provenance) | Replay execution | $0.00 |

## The estimate formula

`TargetPricing` holds `input_usd_per_1m`, `output_usd_per_1m` and an optional `fixed_usd_per_request`:

```text
cost = fixed_usd_per_request
     + tokens_in  / 1,000,000 × input_usd_per_1m
     + tokens_out / 1,000,000 × output_usd_per_1m
```

```python
from decimal import Decimal
from runport.targets.base import TargetPricing

pricing = TargetPricing(input_usd_per_1m=Decimal("0.10"), output_usd_per_1m=Decimal("0.40"))
print(pricing.calculate_cost(1200, 300))
```

All money is handled as `Decimal`. Ceilings are quantized to two decimal places.

## Booking

During a live run, spend is booked to the append-only ledger after each case:

- a known cost is booked with its basis;
- local execution is booked at $0.00 as `UNAVAILABLE`;
- a billed request with unknown cost is booked as `UNRESOLVED`, and live runs stop until you reconcile it.

## Cost per 1,000 cases

```python
from decimal import Decimal
from runport.scorers.performance import CostPer1kScorer

r = CostPer1kScorer(max_cost_per_1k_usd=Decimal("2.00")).evaluate(Decimal("0.0350"), case_count=25)
print(r.score, r.passed)   # projected USD per 1,000 cases
```

A missing total cost gives `None`.

## Auditing

```bash
uv run runport budget status    # ceilings, spend and remaining balances
uv run runport budget audit     # reconcile ledger with stored results (read-only)
```

`budget audit` writes `reports/budget_reconciliation_*.md` and `.json`. See [Budget commands](/cli-budget).

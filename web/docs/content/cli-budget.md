---
title: Budget commands
description: Inspect, audit and reconcile the spend ledger, and change the pilot ceiling.
---

```bash
runport budget COMMAND
```

## status

```bash
runport budget status
```

For each ceiling, shows the configured value, current spend, remaining balance and status.

## audit

```bash
runport budget audit
```

Reconciles the ledger with stored results, read-only, and explains the ledger total versus per-plan guard cost. Writes `reports/budget_reconciliation_*.md` and `.json`.

## policy

```bash
runport budget policy
```

Shows the effective ceilings and the audit trail of operator-authorized pilot-ceiling changes.

## reconcile

```bash
runport budget reconcile --transaction-id TX --amount-usd AMOUNT [--note TEXT]
```

Resolves one `UNRESOLVED` entry with the real amount read from the provider's dashboard. Live runs stay blocked until no unresolved entries remain.

| Option | Required | Meaning |
|---|---|---|
| `-t`, `--transaction-id` | yes | The unresolved ledger entry |
| `-a`, `--amount-usd` | yes | Real amount in USD |
| `--note` | no | For example, the dashboard date |

## raise-pilot-ceiling

```bash
runport budget raise-pilot-ceiling --to AMOUNT --operator NAME
```

Changes the pilot ceiling after an interactive typed phrase. The new value can never exceed the total lifetime ceiling. The total, per-run and per-case ceilings and the ledger are not touched, and the change is recorded with the operator's name.

## purge-simulated

```bash
runport budget purge-simulated
```

Deletes simulated (dry-run) ledger rows and stored dry-run runs. The database is copied first, and real entries are never touched.

See [Budget guardrails](/budget-guardrails) for how the ceilings work.

---
title: Common errors
description: Messages you are likely to see, what they mean, and how to fix them.
---

## "Live runs are blocked until ledger entries are reconciled"

An earlier billed request has unknown cost (`UNRESOLVED`). Find it with `runport budget status`, read the real amount from your provider's dashboard, then:

```bash
uv run runport budget reconcile --transaction-id TX --amount-usd AMOUNT
```

## "Projected spend ... exceeds the per-run ceiling" / "total budget ceiling" / "pilot evaluation ceiling"

The preflight check refused a request. Check `runport budget status`. Raise the pilot ceiling with `runport budget raise-pilot-ceiling`, or edit the ceilings in `runport.yaml`. See [Budget guardrails](/budget-guardrails).

## "Unknown-price target ... requires a positive per-case spend cap"

A live plan includes a target without pricing and `budget.per_case_usd` is 0. Set a positive `per_case_usd`, or give the target a `TargetPricing`.

## "Live run refused: Confirmation phrase mismatch"

The typed phrase must match exactly, including the model ID. Copy it from the prompt.

## "Non-interactive terminal cannot provide live confirmation"

Live runs need a terminal for the typed phrase. In automation, use a `TokenApprover` with `token_approver_enabled: true`; see [Approval policies](/approval-policies#automation).

## "Whole-batch privacy gate rejected case ..."

A case contains a forbidden field name (by default `phone`, `email`, `ssn`, `password`, `token`, `api_key`). Remove or rename the field; the whole batch is refused until no case contains one.

## "Secret or API key detected in workspace configuration"

`runport.yaml` contains a plain-text secret. Remove it and use an environment variable. See [Workspace file](/workspace-file#no-secrets-in-the-file).

## "Records claiming VERIFIED status must specify an authoritative reference_source"

A case is marked `VERIFIED` without a citation. Add `verification.reference_source`, or set the status to `UNVERIFIED`.

## "Workspace configuration already exists"

`runport init` will not overwrite `runport.yaml`. Use `--force` to replace it.

## "Audited knowledge-base records not found under data/audit/"

`benchmark-rag` needs audited knowledge-base files that this release does not ship. See [RAG benchmarks](/rag-benchmarks#prerequisite-an-audited-knowledge-base).

## "Dataset not found at ..."

`create_execution_plan` could not find the dataset file. Check the path relative to where you run the command.

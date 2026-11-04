---
title: Approval policies
description: How live runs are approved, and how approvals are bound to a plan.
---

No live request is sent without explicit approval. Runport has three approvers, all in `runport.core.approvers`, and every one refuses by raising `LiveNotAuthorizedError`.

## In the CLI

`runport benchmark --live`, `benchmark-rag --live` and `smoke-test --live` print a summary and ask you to type an exact phrase:

```text
RUN LIVE google/gemini-3.5-flash-lite
```

Anything else, or a non-interactive terminal, refuses the run. The CLI has no flag to pre-approve a run.

## Approvers for GenericRunner

| Approver | Mode | Approves when |
|---|---|---|
| `InteractiveApprover` | `interactive` | You type `CONFIRM LIVE BENCHMARK` followed by the first 8 characters of the plan fingerprint, in a terminal |
| `TokenApprover` | `token` | The token equals the recomputed plan fingerprint, `token_approver_enabled` is `true`, and the token has not been used before |
| `ModalApprover` | `modal` | The fingerprint confirmed in the web dashboard matches the plan |

```python
from runport.core.approvers import InteractiveApprover

results = runner.execute_plan(plan, targets, cases, approver=InteractiveApprover())
```

## Why fingerprints

The fingerprint covers the targets, dataset hash, case count, budget cap and prompt-template hash. Change any of them after approving and the fingerprint no longer matches, so the run is refused. A token approval is single-use. See [Runs and plans](/runs-and-plans#the-plan-fingerprint).

## Automation

To approve from automation, enable the token approver in `runport.yaml`:

```yaml
approver:
  default_mode: "token"
  token_approver_enabled: true
```

and pass a `TokenApprover` with the plan's fingerprint. With `token_approver_enabled: false` (the default), token approval is refused.

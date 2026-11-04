---
title: Token usage
description: Where token counts come from, and what happens when a provider does not report them.
---

## Source of token counts

Token counts are taken from what the provider reports. Runport does not estimate them.

| Target | `tokens_in` / `tokens_out` from |
|---|---|
| OpenRouter, OpenAI-compatible | `usage.prompt_tokens` / `usage.completion_tokens` |
| Ollama, HTTP workflows, Python callables | Whatever the response or your function provides, else `None` |
| Replay fixtures | `tokens_in`/`prompt_tokens` and `tokens_out`/`completion_tokens` |

OpenRouter responses can also report reasoning tokens (`completion_tokens_details.reasoning_tokens`), which Runport keeps separately.

## Missing counts stay missing

If a provider omits usage, the counts stay `None`. This matters for cost: an `ESTIMATED` cost needs both reported token counts and a price, so missing tokens lead to `UNAVAILABLE` or, for a billed request, `UNRESOLVED`. See [Cost analysis](/cost-analysis).

## Where to see them

Per-case token counts are stored with each result (`prompt_tokens`, `completion_tokens`) and included in [trace exports](/exporting-traces).

## Preflight

Before each live request, the preflight stage checks the request's worst-case cost against every ceiling. For a priced target, the worst case is the price of 1,000 input and 500 output tokens; for an unpriced target, it is the per-case ceiling. See [Budget guardrails](/budget-guardrails#preflight).

---
title: Provider errors
description: How Runport retries, which failures it records, and what each one means for spend.
---

## Retries

HTTP transports retry only transient failures, a bounded number of times:

| Status | Retried |
|---|---|
| `408` request timeout | yes |
| `429` rate limited | yes |
| `500`, `502`, `503`, `504` | yes |
| `524`, `529` (treated like 504 and 503) | yes |
| any other 4xx (for example `400`, `401`, `403`, `404`) | no |

The OpenRouter transport backs off exponentially from 1 s to at most 8 s and makes at most 5 attempts. It honours a `Retry-After` header given in seconds; date-form values are not trusted. Connectors take `max_retries` (default 3).

## How failures are recorded

| Situation | Case status |
|---|---|
| Rate limited after retries | `rate_limited` |
| Key rejected | `unauthorized` |
| Timed out | `timeout` |
| Any other exception | `failed` |
| Empty output | `invalid_output` |

Failures stay in the denominator of every metric; they are never dropped.

## Failures and spend

A timed-out or failed request may still have been billed upstream. Ceilings apply to every attempt, and a billed request that returns no usable cost is booked as `UNRESOLVED`, which blocks further live runs until reconciled. See [Budget guardrails](/budget-guardrails#unresolved-spend).

## Missing key

If `OPENROUTER_API_KEY` is not set, live OpenRouter runs fail before sending anything. Check with:

```bash
uv run runport api-preflight
```

## Blocked URLs

Requests to cloud metadata or link-local addresses are always refused, and loopback or private addresses are refused unless the connector allows them. See [Custom HTTP providers](/custom-http#network-safety).

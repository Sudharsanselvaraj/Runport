---
title: OpenRouter
description: Benchmark hosted models through OpenRouter from the CLI, with catalog pricing and provider-reported cost.
---

OpenRouter is the provider behind the CLI's live modes: `runport benchmark --live`, `runport benchmark-rag --live` and `runport smoke-test --live` all send requests to OpenRouter.

## Set your key

Export the key in your shell, or put it in a `.env` file in the project root:

```bash
export OPENROUTER_API_KEY="..."
```

A shell export takes precedence over `.env`. Runport restricts `.env` to `0600` permissions on POSIX systems. Check what Runport sees, without revealing the key and without sending a request:

```bash
uv run runport api-preflight
```

## Choose models

Models are addressed by their OpenRouter ID, for example `google/gemini-3.5-flash-lite` (the CLI default). List the registered candidates and their attributes:

```bash
uv run runport models roster
```

## Run a live benchmark

```bash
uv run runport benchmark --live --model google/gemini-3.5-flash-lite --split TEST
```

You are asked to type an exact phrase before anything is sent. Local ceilings still apply; see [Budget guardrails](/budget-guardrails).

## How cost is recorded

| Situation | Recorded cost |
|---|---|
| OpenRouter reports `usage.cost` and the unit is verified as USD | Provider-reported (`ACTUAL`) |
| Tokens reported and a verified catalog price exists for the route | Catalog estimate (`ESTIMATED`) |
| Neither | `UNAVAILABLE` |

Catalog prices come from OpenRouter's `/api/v1/models` endpoint, are converted to USD per 1M tokens with `Decimal`, and carry a source and check date.

## Retries

The OpenRouter transport retries only statuses `408`, `429`, `500`, `502`, `503`, `504`, `524` and `529`, with exponential backoff (1 s base, 8 s maximum) and at most 5 attempts. A valid `Retry-After` in seconds is honoured. See [Provider errors](/provider-errors).

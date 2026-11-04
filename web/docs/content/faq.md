---
title: FAQ
description: Short answers to common questions about Runport.
---

## Is Runport free?

Yes. It is open source under the Apache 2.0 licence. You pay only your model providers, and only up to the ceilings you set.

## Does Runport send telemetry?

No. There is no analytics, tracking or phone-home code. Datasets, prompts, traces and the ledger stay on your machine; the only network requests are the ones you approve.

## Can I use it without an API key?

Yes. Replay runs, Ollama, Python targets and the whole offline test suite need no key.

## How does it stop runaway spending?

Every live request is checked against the per-run, total and pilot ceilings before it is sent, and a request with unknown cost blocks further live runs until it is reconciled. See [Budget guardrails](/budget-guardrails).

## Why doesn't it treat model agreement as accuracy?

Two models can agree and both be wrong. Agreement is reported as agreement (Cohen's kappa); accuracy needs human-approved labels.

## Can I benchmark my Dify, n8n or LangGraph workflow?

Yes, from Python. Dify is supported; Flowise, Langflow, n8n and LangGraph are experimental. Any other workflow with an HTTP endpoint works through the HTTP connector. See [Integrations](/dify).

## Can I run it in CI?

Yes. Replay runs and the test suite run offline, need no key and book $0.00.

## Which Python versions are supported?

3.11, 3.12 and 3.13.

## Where is my data stored?

In `data/runport.db` (SQLite, WAL mode) and `reports/`, relative to your workspace.

## Where do I report a bug?

Open an issue on [GitHub](https://github.com/Sudharsanselvaraj/runport/issues). For security issues, follow `SECURITY.md` in the repository instead.

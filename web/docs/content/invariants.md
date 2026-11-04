---
title: Invariants
description: The ten rules Runport's core never breaks, and what each means in practice.
---

These rules are enforced in code and covered by the test suite. Contributions must not weaken them.

## 1. Null is not 0

Missing tokens, latency, confidence or cost stay `None` / `UNAVAILABLE`. A scorer with nothing to score returns `score=None`, not `0`.

## 2. Fixed provenance vocabulary

Cost always carries one of four labels:

| Label | Meaning |
|---|---|
| `ACTUAL` | Exact provider-reported USD spend |
| `ESTIMATED` | Verified catalog rate × reported tokens |
| `UNRESOLVED` | Billed request with unknown cost |
| `UNAVAILABLE` | Unpriced or local execution, booked at $0.00 |

## 3. Strict guard order

Authorization → privacy gate → preflight budget and context check → transport → validation → persistence → spend booking. See [Architecture](/architecture#the-guard-order).

## 4. Unresolved spend blocks execution

An `UNRESOLVED` ledger entry blocks every further live run until it is reconciled with `runport budget reconcile`. See [Budget guardrails](/budget-guardrails#unresolved-spend).

## 5. Plan fingerprint

Approvals bind to a SHA-256 fingerprint of targets, dataset hash, prompt-template hash and budget cap. Stale or mismatched approvals are rejected.

## 6. Immutable sources

Datasets are hashed with SHA-256 before and after evaluation.

## 7. Secret scrubbing

API keys, bearer tokens and secrets are scrubbed from request logs, trace events and exports, and `runport.yaml` refuses plain-text secrets.

## 8. Agreement is not correctness

Model-to-model consensus (for example Cohen's kappa) is reported as agreement, never as accuracy.

## 9. No tuning on held-out splits

Thresholds and hyper-parameters are calibrated on `DEV` only, frozen, and applied unchanged to `TEST`.

## 10. No simulation in core modules

Test doubles live only under `tests/`. Replay runs are isolated, carry provenance `REPLAYED` and book $0.00.

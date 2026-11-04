---
title: Datasets
description: The JSONL case schema, confidentiality classes, splits, and how Runport validates and protects datasets.
---

Datasets are JSONL files: one JSON object per line, one evaluation case per object. The bundled examples live in `data/evaluation/`.

## The case schema

```json
{
  "id": "eval-seed-001",
  "query": "What are the entry requirements for ...?",
  "expected_answer": "Candidates must possess ...",
  "programme_category": "Accounting",
  "difficulty": "MEDIUM",
  "classification": "SYNTHETIC",
  "split": "TEST",
  "verification": {
    "status": "VERIFIED",
    "reference_source": "Prospectus 2026",
    "verifier": "Academic Reviewer"
  },
  "tags": ["requirements"]
}
```

| Field | Required | Values / default |
|---|---|---|
| `id` | yes | Unique case identifier |
| `query` | yes | The prompt sent to the target |
| `expected_answer` | no | Ground-truth answer |
| `programme_category` | no | Free text, default `General` |
| `difficulty` | no | `EASY`, `MEDIUM` (default), `HARD`, `EDGE_CASE` |
| `classification` | no | `PUBLIC`, `SYNTHETIC`, `INTERNAL`, `CONFIDENTIAL`, `UNCLASSIFIED` (default) |
| `split` | no | `TRAIN`, `DEV`, `TEST`, `UNASSIGNED` (default) |
| `verification` | no | `status` (`UNVERIFIED` default, `VERIFIED`, `DISPUTED`), `reference_source`, `verifier`, `verified_at`, `notes` |
| `expected_claims` | no | Facts the answer must contain |
| `expected_context`, `expected_retrieval_keywords`, `relevant_record_ids` | no | Used by [RAG benchmarks](/rag-benchmarks) |
| `abstention_expected` | no | `true` when the right answer is to decline |
| `tags`, `metadata` | no | Free-form |

> [!IMPORTANT]
> A record with `verification.status` set to `VERIFIED` must name a `reference_source`; otherwise it fails validation.

## Confidentiality classes

Classification defaults to `UNCLASSIFIED`, which is fail-closed. Only `PUBLIC` and `SYNTHETIC` records may be routed to external model APIs; `INTERNAL`, `CONFIDENTIAL` and `UNCLASSIFIED` records are blocked before network dispatch.

## Splits

`TRAIN` is for tuning, `DEV` for calibrating thresholds, and `TEST` is held out. Thresholds chosen on `DEV` are frozen and applied unchanged to `TEST`; see [Classification](/classification#thresholds-are-chosen-on-dev-only). CLI benchmarks run on `TEST` by default (`--split DEV` or `--split ALL` to change).

## Validating a dataset

```bash
uv run runport validate-dataset path/to/cases.jsonl
```

The command reports per-split counts, how many records are eligible for external dispatch, and the result of cross-split leakage and n-gram overlap detection. Leakage checks run by default; pass `--no-check-leakage` to skip them.

## Protections

- **Immutability.** Plans hash the dataset with SHA-256; a changed file produces a different plan fingerprint. See [Reproducibility](/reproducibility).
- **Privacy gate.** Before a live run sends anything, every case is checked for forbidden field names (by default `phone`, `email`, `ssn`, `password`, `token`, `api_key`). One match aborts the whole batch. See [Workspace file](/workspace-file#telemetry).

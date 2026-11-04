---
title: RAG evaluation
description: Retrieval and generation metrics, and how Runport attributes a failure to one of them.
---

RAG evaluation scores retrieval and generation separately, then attributes each case's outcome. It is used by [`runport benchmark-rag`](/rag-benchmarks) and lives in `runport.rag`.

## Retrieval metrics

| Metric | Meaning |
|---|---|
| `recall_at_k` | Share of relevant records retrieved in the top k |
| `precision_at_k` | Share of the top k that are relevant |
| `reciprocal_rank` | 1 / rank of the first relevant record |
| `retrieval_hit` | Whether any relevant record was retrieved |
| `retrieval_hit_rate`, `retrieval_precision` | Diagnostic keyword-based hit rate and precision |

Relevance comes from each case's `relevant_record_ids` and `expected_retrieval_keywords`.

## Generation metrics

`RAGSystemEvaluator.evaluate_generation` returns:

- **answer correctness**: agreement between the generated answer and `expected_answer`;
- **groundedness**: how far the answer is supported by the retrieved chunks.

For cases with `abstention_expected: true`, **abstention correctness** records whether the system declined.

## Failure attribution

Each case gets one label:

| Label | Rule |
|---|---|
| `SYSTEM_SUCCESS` | Retrieval hit rate ≥ 0.5 and correctness ≥ 0.6 and groundedness ≥ 0.5 |
| `GENERATION_FAILURE` | Retrieval passed, generation failed |
| `RETRIEVAL_FAILURE` | Both failed |
| `PARAMETRIC_MEMORY_RESCUE` | Retrieval failed but the answer was still right |

## Run-level report

`RAGBenchmarkReport` holds the means of the metrics above (`mean_recall_at_k`, `mean_precision_at_k`, `mean_reciprocal_rank`, `verified_retrieval_hit_rate` and others) plus counts of verified and unresolved cases.

## Offline example

```bash
uv run python examples/rag/run.py
```

Scores decoupled retrieval (Recall@1) against a small synthetic corpus.

---
title: RAG benchmarks
description: Evaluate retrieval and generation separately with runport benchmark-rag.
---

`runport benchmark-rag` evaluates a retrieval-augmented pipeline on two axes, retrieval and generation, so a wrong answer can be attributed to the part that failed.

```bash
uv run runport benchmark-rag [--model ID] [--dataset FILE] [--split TEST|DEV|ALL] [--live]
                              [--compare-with ID] [--top-k N] [--exclude-defective | --include-all]
```

| Option | Default | Meaning |
|---|---|---|
| `-m`, `--model` | `google/gemini-3.5-flash-lite` | Generator model (OpenRouter ID) |
| `-d`, `--dataset` | `data/evaluation/verified_rag_benchmark.jsonl` | Cases with expected context and keywords |
| `-s`, `--split` | `TEST` | `TEST`, `DEV` or `ALL` |
| `--live` | off | Send real requests; without it nothing is sent |
| `-c`, `--compare-with` | none | A second model for side-by-side comparison |
| `-k`, `--top-k` | `2` | Chunks retrieved per case |
| `--exclude-defective` / `--include-all` | exclude | Leave known contradictory or incomplete records out of the index |

## Prerequisite: an audited knowledge base

The retriever is a keyword BM25 retriever (`KeywordBM25Retriever`) built from audited knowledge-base records at:

- `data/audit/parsed_records_general_kb.jsonl`
- `data/audit/parsed_records_programmes_kb.jsonl`

If neither file exists, the command stops; it never falls back to the evaluation passages.

> [!WARNING]
> The error message suggests running `runport audit-kb`. That command is not part of this release, and the repository does not ship `data/audit/`. Until it does, `benchmark-rag` can only run where you have produced these files yourself. The offline example `examples/rag/run.py` shows decoupled retrieval scoring without them.

## What it measures

Per case: recall@k, precision@k, reciprocal rank and a retrieval hit; answer correctness and groundedness; and, for cases that expect the system to decline, abstention correctness. Per run: the means, plus counts of verified and unresolved cases. See [RAG evaluation](/rag-evaluation).

## Leakage warning

Before running, the command checks the evaluation cases against the index and prints a warning naming any leaked case IDs.

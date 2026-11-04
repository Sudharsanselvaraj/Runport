---
title: Benchmarks
description: The kinds of benchmark Runport runs and the command or API that runs each.
---

A benchmark in Runport is a dataset of cases, one or more targets, and a way of scoring their outputs. There are three ways to run one.

| Benchmark | How to run it | Targets |
|---|---|---|
| Question answering | `runport benchmark` | OpenRouter models by ID |
| RAG (retrieval + generation) | `runport benchmark-rag` | OpenRouter models, with a local BM25 retriever |
| Any target | `GenericRunner` in Python | Any `Target`: connectors, workflows, Python callables, plugins |

## CLI benchmarks

`runport benchmark` evaluates one OpenRouter model on a JSONL dataset split. It runs in one of three modes:

- **Explain** (default): prints what it would do and sends nothing.
- **Replay** (`--replay`): offline, provenance `REPLAYED`, `$0.00`.
- **Live** (`--live`): real requests after a typed confirmation, tracked against your ceilings.

See [Executing benchmark runs](/executing-runs) and [RAG benchmarks](/rag-benchmarks).

## Python benchmarks

To benchmark anything that is not an OpenRouter model (a Dify app, an HTTP workflow, a local Ollama model, your own function), wrap it as a target and run it with `GenericRunner`. The runner applies the full guard order. See [Creating benchmarks](/creating-benchmarks).

## Scoring

The CLI benchmark scores answers with a built-in heuristic (see [Understanding results](/understanding-results#how-the-cli-benchmark-scores-answers)). For anything more specific, apply a scorer from `runport.scorers` to the outputs. See [Scorers](/scorers).

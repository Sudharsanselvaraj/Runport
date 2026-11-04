---
title: Executing benchmark runs
description: Run runport benchmark in explain, replay and live modes, and what each mode does.
---

```bash
uv run runport benchmark [--model ID] [--dataset FILE] [--split TEST|DEV|ALL] [--live | --replay]
```

| Option | Default | Meaning |
|---|---|---|
| `-m`, `--model`, `--target` | `google/gemini-3.5-flash-lite` | OpenRouter model ID |
| `-d`, `--dataset` | `data/evaluation/synthetic_seed_eval.jsonl` | JSONL dataset |
| `-s`, `--split` | `TEST` | `TEST`, `DEV` or `ALL` |
| `--live` | off | Send real requests to OpenRouter |
| `--replay` | off | Run offline with provenance `REPLAYED` and $0.00 spend |
| `-f`, `--fixtures` | the dataset file | Replay only: JSONL of recorded outputs to score |

## Explain mode (default)

With neither flag, the command describes the run it would perform and sends nothing. Use it to check the model, dataset and split before spending.

## Replay mode

```bash
uv run runport benchmark --replay --dataset data/evaluation/synthetic_seed_eval.jsonl
```

Replay mode needs no key and no network. The run is stored with provenance `REPLAYED` and books $0.00, so it is safe in CI.

Replay scores **recorded outputs**, the same way a live run is scored. Point it at a JSONL file of recordings with `--fixtures` (one object per case: `id`, `output_text`, and optionally `latency_ms` and token counts); without `--fixtures` it looks for recordings in the dataset file itself.

```bash
uv run runport benchmark --replay --dataset cases.jsonl --fixtures recorded.jsonl
```

> [!NOTE]
> A case with no recording is not scored: its output, latency and scores stay empty and are left out of every mean. Nothing is substituted, not the expected answer and not a fixed timing. The bundled seed dataset carries no recordings, so replaying it on its own reports `0 / N` recorded outputs and no scores.

## Live mode

```bash
uv run runport benchmark --live --model google/gemini-3.5-flash-lite
```

Before any request, Runport prints a summary and asks you to type an exact phrase of the form:

```text
RUN LIVE google/gemini-3.5-flash-lite
```

Anything else refuses the run and the command exits with code 1. A live run is also refused if:

- `OPENROUTER_API_KEY` is not set;
- an `UNRESOLVED` ledger entry exists ([reconcile it first](/cli-budget#reconcile));
- a case would push spend past a ceiling ([Budget guardrails](/budget-guardrails)).

Each case is scored as it completes; see [Understanding results](/understanding-results#how-the-cli-benchmark-scores-answers).

## Smoke test

```bash
uv run runport smoke-test [--model ID] [--cases N] [--live]
```

Offline, `smoke-test` verifies a synthetic plan and dispatches nothing. With `--live` it asks for the typed confirmation; in this release it stops after approval and sends no requests.

## After a run

- `runport compare-runs RUN_A RUN_B` compares two stored runs. See [Comparing runs](/comparing-runs).
- `runport export-traces` exports redacted traces. See [Exporting reports](/exporting-traces).

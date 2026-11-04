---
title: Reproducibility
description: Plan fingerprints, dataset hashing, fixed seeds and deterministic replay.
---

## Plan fingerprints

Every execution plan carries a SHA-256 fingerprint over its sorted target IDs, dataset hash, case count, budget cap and prompt-template hash. Two runs with the same fingerprint used the same inputs. The fingerprint is stored with each run (in the run's notes) and is what approvals bind to. See [Runs and plans](/runs-and-plans#the-plan-fingerprint).

## Dataset hashing

Datasets are hashed with SHA-256 before evaluation. Any edit, including reordering lines, changes the hash and therefore the fingerprint. `runport.scorers.stats.sha256_file` hashes a file in 1 MB chunks if you need to record a hash yourself.

## Fixed seeds

Statistical helpers in `runport.scorers.stats` are deterministic:

- the default seed is `20261021`;
- `rng_for(label, seed)` derives an independent generator per label, so adding one analysis does not change another's random stream;
- bootstrap intervals use 2,000 resamples by default.

## Deterministic replay

`ReplayRunner` replays recorded outputs. Results carry provenance `REPLAYED` and cost `$0.00`.

```python
from runport.runs.replay import ReplayRunner

runner = ReplayRunner(fixtures="examples/replay-demo/fixtures.jsonl", target_id="mock-replay-model")
res = runner.replay_case("rep-001", {"id": "rep-001", "query": "What is the capital of France?"})
print(res.provenance, res.output_text, res.cost_usd)   # REPLAYED Paris 0.0000
```

A fixture is one JSON object per line, matched to cases by `case_id`, `id` or `input_id`:

```json
{"id": "rep-001", "query": "What is the capital of France?", "output_text": "Paris", "status": "success", "tokens_in": 7, "tokens_out": 1, "latency_ms": 120.5}
```

The output is read from `output_text`, `output`, `response` or `text`; tokens from `tokens_in`/`prompt_tokens` and `tokens_out`/`completion_tokens`.

## Reproducible exports

Trace exports are byte-identical for the same selection, sources, schema version and export timestamp. See [Exporting reports](/exporting-traces).

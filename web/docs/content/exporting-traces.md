---
title: Exporting reports
description: Export redacted, reproducible traces as JSONL, CSV or ZIP, and import Langfuse traces.
---

## Export traces

```bash
uv run runport export-traces -f zip
```

Exports are built read-only from the stored prediction records, the request-event log and approved labels. They send nothing and never overwrite an existing file. The default destination is `reports/exports`.

| Format | Contents |
|---|---|
| `jsonl` | One trace record per line |
| `csv` | One trace record per row |
| `zip` | Per-model files, a comparison file and a manifest |

Filter with `--model`, `--run` and `--status` (each repeatable) and `--task`. See [Commands](/cli-commands#export-traces).

## Redaction

Exports are redacted by default: no secrets and no restricted fields. Raw text is included only with a written authorization from the data owner that names the owner, the scope and the date.

## Reproducibility

The same selection, sources, schema version and export timestamp produce byte-identical files. A model that never ran appears only in the manifest's coverage, never as a trace row.

## Budget reports

```bash
uv run runport budget audit
```

writes `reports/budget_reconciliation_*.md` and `.json`. See [Budget commands](/cli-budget#audit).

## Import Langfuse traces

```bash
uv run runport import-traces langfuse_export.json --output-dir reports/
```

Reads a redacted Langfuse JSON or CSV export and diagnoses candidate RAG failure modes, keeping hypotheses at or above `--min-confidence` (default 0.5). With `--output-dir`, it writes CSV and Markdown reports.

> [!WARNING]
> `reports/` holds run outputs. Keep it out of version control; the repository's `.gitignore` already excludes it.

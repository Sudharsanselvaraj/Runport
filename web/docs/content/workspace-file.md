---
title: Workspace file
description: The runport.yaml schema, section by section, with defaults.
---

A workspace is configured by one YAML file in the project root. Runport looks for `runport.yaml`, `runport.yml`, `workbench.yaml` or `workbench.yml`, in that order, and uses built-in defaults when none exists. `runport init` writes a complete file.

## Example

```yaml
schema_version: "1.0"
name: "my-evaluation-workspace"

budget:
  total_usd: 5.00
  per_run_usd: 1.00
  per_case_usd: 0.05
  pilot_usd: 1.00
  require_priced: false
  retry_buffer_pct: 0.05

approver:
  default_mode: "interactive"
  token_approver_enabled: false

telemetry:
  local_logging: true
  redact_secrets: true
  forbidden_fields: ["phone", "email", "ssn", "password", "token", "api_key"]

storage:
  data_dir: "data"
  db_filename: "runport.db"
  reports_dir: "reports"

catalog_sources: []
targets: []
```

## budget

| Field | Default | Meaning |
|---|---|---|
| `total_usd` | `5.00` | Lifetime ceiling for the workspace |
| `per_run_usd` | `1.00` | Ceiling for any single request projection in a run |
| `per_case_usd` | `0.05` | Worst-case estimate for unpriced targets |
| `pilot_usd` | `1.00` | Ceiling for pilot evaluations |
| `require_priced` | `false` | Refuse live runs on targets without a verified price |
| `retry_buffer_pct` | `0.05` | Headroom reserved for retries |

Amounts are quantized to two decimal places. See [Budget guardrails](/budget-guardrails).

## approver

| Field | Default | Meaning |
|---|---|---|
| `default_mode` | `interactive` | `interactive`, `token` or `modal` |
| `token_approver_enabled` | `false` | Allow fingerprint-token approval for automation |

See [Approval policies](/approval-policies).

## telemetry

Local logging and privacy only; nothing is sent anywhere.

| Field | Default | Meaning |
|---|---|---|
| `local_logging` | `true` | Append-only SQLite event log |
| `redact_secrets` | `true` | Scrub keys and bearer tokens from logs |
| `forbidden_fields` | `phone`, `email`, `ssn`, `password`, `token`, `api_key` | Case fields that abort a run at the privacy gate |

## storage

| Field | Default | Meaning |
|---|---|---|
| `data_dir` | `data` | Datasets and the database |
| `db_filename` | `runport.db` | SQLite database (WAL mode) |
| `reports_dir` | `reports` | Reports and exports |

## catalog_sources and targets

`catalog_sources` lists paths to model catalogs or plugin references. `targets` lists target entries (`id`, `type`, `endpoint`, `model`, `headers`, `options`). See [Provider configuration](/provider-configuration) for what reads them today.

## No secrets in the file

Loading fails if any key containing `api_key`, `secret`, `private_key`, `password` or `access_token` has a plain string value. A value that starts with `$` (an environment-variable reference) is allowed. Put keys in the environment; see [Environment variables](/environment-variables).

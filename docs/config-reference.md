# Workspace Configuration Reference

Runport workspaces are configured via `runport.yaml` (or `runport.yml`) located in your project root.

---

## Example `runport.yaml`

```yaml
schema_version: "1.0"
name: "my-evaluation-workspace"

budget:
  total_usd: 5.00
  pilot_usd: 1.00
  per_run_usd: 1.00
  per_case_usd: 0.05
  require_priced: false
  retry_buffer_pct: 0.05

approver:
  default_mode: "interactive"
  token_approver_enabled: false

telemetry:
  local_logging: true
  redact_secrets: true
  forbidden_fields:
    - "phone"
    - "email"
    - "ssn"
    - "password"
    - "token"
    - "api_key"

storage:
  data_dir: "data"
  db_filename: "runport.db"
  reports_dir: "reports"

targets:
  - id: "gemini-flash"
    type: "openrouter"
    model: "google/gemini-3.5-flash-lite"
  - id: "custom-api"
    type: "http_workflow"
    endpoint: "http://127.0.0.1:8080/predict"
    headers:
      Content-Type: "application/json"
```

---

## Configuration Schema

### `budget` Section

Controls spend caps and preflight pricing requirements.

| Field | Type | Default | Description |
|---|---|---|---|
| `total_usd` | Decimal | `5.00` | Lifetime spend ceiling across the entire workspace. |
| `pilot_usd` | Decimal | `1.00` | Spend ceiling for pilot evaluations. |
| `per_run_usd` | Decimal | `1.00` | Hard cap on spend for any individual execution run. |
| `per_case_usd` | Decimal | `0.05` | Hard cap on spend for a single input record. |
| `require_priced` | bool | `false` | If true, rejects any target whose catalog pricing is missing. |
| `retry_buffer_pct` | Decimal | `0.05` | 5% budget headroom allocated for transient network retries. |

---

### `approver` Section

Defines the gatekeeper policy for live API executions.

| Field | Type | Default | Description |
|---|---|---|---|
| `default_mode` | string | `"interactive"` | Approval mode: `"interactive"`, `"token"`, or `"modal"`. |
| `token_approver_enabled` | bool | `false` | When true, permits non-interactive `--approve <fingerprint>` in automation. |

---

### `telemetry` Section

Local privacy and confidentiality settings.

| Field | Type | Default | Description |
|---|---|---|---|
| `local_logging` | bool | `true` | Enables append-only SQLite WAL audit events. |
| `redact_secrets` | bool | `true` | Automatically scrubs keys, bearer tokens, and hashes from logs. |
| `forbidden_fields` | list[str] | `["phone", "email", "ssn", "password", "token", "api_key"]` | Attribute names rejected by the pre-transport privacy gate. |

---

### `storage` Section

Paths for local storage artifacts.

| Field | Type | Default | Description |
|---|---|---|---|
| `data_dir` | string | `"data"` | Path to evaluation data and SQLite database files. |
| `db_filename` | string | `"runport.db"` | SQLite database filename (uses WAL mode). |
| `reports_dir` | string | `"reports"` | Output directory for markdown summaries and exported traces. |

---

### `targets` Section

Defines candidate endpoints or workflows to benchmark.

| Field | Type | Default | Description |
|---|---|---|---|
| `id` | string | *required* | Unique identifier for target reference. |
| `type` | string | *required* | Connector type (`openrouter`, `http_workflow`, `dify`, `flowise`, `langflow`, `n8n`, `python_target`, `ollama`). |
| `endpoint` | string | `null` | Base URL or invocation endpoint. |
| `model` | string | `null` | Specific model identifier if required by adapter. |
| `headers` | dict | `{}` | Custom HTTP headers. Values may reference environment variables. |
| `options` | dict | `{}` | Target-specific connector settings. |

---

## Invariant: Zero Secrets in Config

> [!CAUTION]
> Runport strictly rejects configuration files containing credentials (`api_key`, `secret`, `password`, `access_token`, etc.). Always inject keys via environment variables (e.g. `OPENROUTER_API_KEY`).

# Safety, Privacy & Security Architecture

Runport is engineered from the ground up to prevent data leakage, eliminate unexpected API billing, and protect local infrastructure.

---

## 1. Secret Scrubbing & Redaction

API keys, access tokens, bearer headers, and passwords must never leak into log files, SQLite databases, traces, or terminal displays.

Runport enforces automated redaction through regex pattern matchers and key blacklist filters:
- Upstream HTTP Authorization headers (`Bearer ...`) are replaced with `[REDACTED]`.
- API keys matching common patterns (`sk-or-v1-...`, `sk-...`, `Bearer ...`) are scrubbed before event emission.
- Workspace configuration files (`runport.yaml`) are checked on load; if any secret key is detected in plain text, loading fails immediately.

---

## 2. Pre-Transport Privacy Gate & Forbidden Fields

Before any case payload is sent to an external model endpoint or custom workflow target, the `GenericRunner` passes the entire batch through the whole-batch Privacy Gate.

By default, the following field names are forbidden:
```yaml
forbidden_fields:
  - "phone"
  - "email"
  - "ssn"
  - "password"
  - "token"
  - "api_key"
```

If any case in the dataset contains a forbidden key, **the entire batch is aborted immediately** before any network connection is opened or compute initiated.

---

## 3. SSRF Safeguards (Server-Side Request Forgery)

When evaluating arbitrary HTTP workflow endpoints or custom webhooks, Runport defends against SSRF vulnerabilities:
- **Cloud Metadata Protection**: Requests to cloud metadata services (e.g. `169.254.169.254`, `metadata.google.internal`) are blocked fail-closed.
- **Loopback and Private Network Checks**: External requests cannot be routed into internal infrastructure unless explicitly authorized.
- **Non-loopback Web UI Guard**: If the local web server binds to a non-loopback interface (e.g. `0.0.0.0`), execution fails unless a secure `RUNPORT_API_TOKEN` environment variable is explicitly provided.

---

## 4. Zero Simulation in Core Modules

Runport strictly enforces no simulation in core packages:
- Test doubles and mocks are quarantined exclusively under `tests/`.
- Replay runs utilize isolated, recorded response records, carry provenance `REPLAYED`, and book `$0.00` spend.
- Live runs only communicate with real endpoints upon receiving explicit cryptographic confirmation.

# Security Policy

Runport is designed with a **local-first, fail-closed, privacy-preserving** security model. This document outlines our security principles and how to report vulnerabilities.

---

## 1. Security Architecture & Safeguards

### Local-First Execution
- Runport runs entirely on your local machine.
- There is **zero external telemetry**, analytics, tracking, or phone-home networking.
- Database records (SQLite WAL), evaluation logs, and configuration remain stored in your local workspace.

### Automatic Secret Scrubbing
- All HTTP transports, CLI outputs, trace event tails, and diagnostic exports automatically scrub API keys, Bearer tokens, and sensitive headers matching known provider key patterns (`sk-...`, `Bearer ...`).
- Raw keys and secrets are never stored in the database or written to trace files.

### SSRF Protection
- Outbound HTTP transports validate target URLs to mitigate Server-Side Request Forgery (SSRF).
- Requests to cloud metadata services (`169.254.169.254`) and unauthorized loopback destinations are rejected fail-closed.

### Fail-Closed Budget Caps
- Live execution is blocked if budget ceilings are exceeded or if unresolved ledger transactions exist.
- Plan fingerprints guarantee that models, endpoints, and datasets cannot be altered mid-run without re-authorization.

---

## 2. Reporting a Vulnerability

If you discover a potential security issue in Runport:

1. **Do not open a public GitHub issue.**
2. Send an email to the repository maintainer via the GitHub security advisory channel or directly to the project maintainer.
3. Include:
   - A description of the issue and potential impact.
   - Minimal reproduction steps, script, or configuration.
   - Any proposed remediation or patches.

We take security seriously and will acknowledge reports promptly, investigate the findings, and release fixes in an advisory update.

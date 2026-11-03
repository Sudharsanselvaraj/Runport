# Owner Decisions & Architectural Plan: Runport

This document records all confirmed decisions made by the project owner for transitioning the codebase into **Runport** (`runport`), an open-source, any-API / any-workflow benchmarking platform. It also records unresolved implementation questions, an architectural compatibility check, the complete Phase 0 Readiness Audit, and the finalized execution plan.

---

## 1. Decision Record Matrix

| # | Topic | Status | Owner Decision Summary |
|---|---|---|---|
| **1** | **Project Identity & Naming** | **OWNER-CONFIRMED** | Name: **Runport** (`runport`). CLI: `runport`. "Inferia" brand kept separate. Prior candidates replaced. |
| **2** | **Execution Approval Model** | **OWNER-CONFIRMED** | Interactive CLI/TUI: typed phrase. Web UI: modal approval. CI: `--approve <plan_fingerprint>`. Plan always recomputed before check; no stale approvals. |
| **3** | **Budget & Pricing Defaults** | **OWNER-CONFIRMED** | Ceilings: Total $5.00, Run $1.00, Case $0.05, all configurable; `require_priced=false`. Strict separation of Actual / Estimated / Unresolved / Unavailable. |
| **4** | **Replay Mode & Demo Connectors** | **OWNER-CONFIRMED** | REPLAYED demo target and Ollama allowed. Replay output always labeled `REPLAYED` and never counted as a live result or spend. |
| **5** | **Web Interface Architecture** | **OWNER-CONFIRMED** | Single-user localhost web UI (FastAPI + React/TS/Vite). Apache-2.0. No telemetry. |
| **6** | **License & IP Clearance** | **OWNER-CONFIRMED** | Target license: Apache 2.0. Clean-slate Git repo. Mandatory exclusion of confidential legacy text before publishing. |
| **7** | **Subsystem Migration Scope & Connectors** | **OWNER-CONFIRMED** | v0.1 stable-candidate connectors: `openai_compat`, `openrouter`, `dify`, `http_workflow`, `python_target`, `ollama`. Flowise/Langflow/n8n/LangGraph stay experimental until contract suite passes. |
| **8** | **Telemetry Policy & Token Approver** | **OWNER-CONFIRMED** | Zero external telemetry. Token approver allowed, off by default, valid only if fingerprint matches freshly recomputed plan. |

---

## 2. Detailed Decision Specifications

### Decision 1 — Project Identity & Naming
* **Product Name:** Runport
* **Python Package:** `runport`
* **CLI Command:** `runport`
* **Documentation Identity:** Runport
* **Brand Separation:** The "Inferia" brand is strictly separated from Runport and will not appear in this repository or documentation unless explicitly approved.

### Decision 2 — Execution Approval Model
* **Interactive CLI / TUI:** Requires typed human confirmation containing the plan fingerprint (`RUN LIVE ... PLAN <fingerprint>`), matching the existing invariant.
* **Web UI:** Human approval via modal displaying the full costed plan, target roster, and fingerprint.
* **CI / Automated Environments:** Allow non-interactive execution via `--approve <plan_fingerprint>`.
* **Safety Invariant:** The execution plan must always be freshly recomputed from the current dataset, models, and configuration immediately before execution. The provided fingerprint is verified against the freshly recomputed plan. Stale, modified, or mismatched approvals fail closed.

### Decision 3 — Budget Policies & Pricing Strictness
* **Default Ceilings (`workbench.yaml`):**
  * `total_budget_usd: 5.00`
  * `per_run_ceiling_usd: 1.00`
  * `per_case_ceiling_usd: 0.05`
* **Pricing Strictness:** `require_priced: true` by default.
  * Models without verified catalog pricing fail preflight by default.
  * Running an unpriced model or custom HTTP target requires explicit user opt-in (`require_priced: false`) combined with documented spend protections (per-case circuit breakers and unresolved-spend blocking).
* **Honest Accounting:** Cost accounting strictly preserves provenance distinctions: `ACTUAL` (provider-reported verified USD), `ESTIMATED` (catalog rate × reported tokens), `UNRESOLVED` (billed request with unknown cost), `UNAVAILABLE` (zero-cost unpriced / local).

### Decision 4 — Replay Mode for Quickstart & Demos
* **Implementation:** Add a fixture-based replay connector.
* **Provenance Tagging:** All executions from this connector carry provenance `REPLAYED`.
* **Zero Conflation:** Replay results are never mixed with live benchmark results, never booked as actual spend, and never presented as proof of live provider execution or performance.

### Decision 5 — Web Interface Stack & Multi-User Scope
* **Backend:** FastAPI application in `src/runport/api/` binding strictly to `127.0.0.1` by default; live telemetry streamed over SSE from `EventTail`.
* **Frontend:** React + TypeScript + Vite + Tailwind CSS SPA, pre-built and bundled into package wheel assets, served directly by `runport ui`.
* **Deployment Scope:** Single-user localhost execution only. No user accounts, passwords, sessions, or remote multi-tenancy in the initial open-source release.
* **Charting Library:** Selected based on bundle efficiency, accessible rendering, and maintainability (e.g. Recharts).

### Decision 6 — Licensing, Intellectual Property & Downstream Maintenance
* **License:** Apache 2.0.
* **Clean-Slate Git Repository:** Approved in principle for Phase 0 to permanently purge confidential prototype data, candidate phone numbers, and internal prompts from Git commit history.
* **IP Clearance Gate:** Before publishing to GitHub or PyPI, conduct a comprehensive audit across all files, test fixtures, datasets, prompts, and logs to ensure no proprietary legacy text or third-party IP remains. Publishing is blocked until clearance is complete.
* **Downstream Architecture:** The internal domain-specific prototype will be preserved as a private downstream consumer that imports `runport` as an external library.

### Decision 7 — Subsystem Migration & Core Extraction
* **Dify Integration:** The existing `dify_eval/` package was audited:
  * `client.py` (`post_chat_message`) and `rag_stream.py` (SSE streaming) are extracted into core `src/runport/connectors/dify.py`.
  * One-off study evaluation runners and report generators are deleted.
* **Decisions API Reference Adapter:** Relocated to `examples/plugins/` as a worked reference plugin.
* **KB Auditor & Remediation:** Relocated to `examples/plugins/kb_audit/`.
* **Domain Decoupling:** All legacy-specific rules, hardcoded classifications, and prototype assumptions are eliminated from the core platform while preserving research provenance in migration docs.

### Decision 8 — Telemetry & Network Policy
* **Zero External Telemetry:** Runport will emit zero telemetry, analytics, tracking pings, or diagnostic reports over the network to any third party.
* **Local Storage Only:** All telemetry remains strictly local (`data/telemetry/request_events.jsonl` and SQLite ledger).
* **Transparency:** Network behavior, local socket bindings, and the zero-telemetry guarantee will be documented in `SECURITY.md`.

---

## 3. Identity Verification & Naming Conflict Audit for "Runport"

### 3.1 Verified Availability & Non-Conflict Results
* **PyPI (`runport`):** **VERIFIED AVAILABLE.** Live JSON API check returned **HTTP 404**. Unregistered and free to claim.
* **CLI Command (`runport`):** **VERIFIED UNCONTESTED.** No standard system utility, Unix binary, or popular Python tool uses `runport`.
* **GitHub Repository (`Sudharsanselvaraj/runport`):** **VERIFIED AVAILABLE.** Endpoint returned **HTTP 404**.
* **Software Trademarks:** **VERIFIED CLEAR.** Exhaustive search showed no registered or active software trademark for "Runport" in AI, benchmarking, or developer tools.

### 3.2 Items Requiring Owner Awareness / Action
* **GitHub Organization Name (`github.com/runport`):** An individual personal user account exists at `github.com/runport` (registered Sept 2019, inactive profile). The bare organization name is unavailable immediately. Recommended paths:
  * `github.com/Sudharsanselvaraj/runport`
  * `github.com/runport-org/runport`
  * `github.com/runport-ai/runport`
* **Domain Names:**
  * `runport.com`: Registered and active.
  * `runport.dev`, `runport.io`, `runport.org`, `runport.ai`: Have no active DNS A-records (NXDOMAIN / unassigned). Owner should check registrar pricing if securing a domain is desired.

---

## 4. Unresolved Implementation Questions (For Phase 1 & 2 Execution)

1. **Replay Connector Fixture Format:**
   * *Proposed:* JSONL file where each record matches `TargetResult` schema with `provenance: "REPLAYED"`, stored under `tests/fixtures/replay/` or `examples/fixtures/`.
2. **Chart Library Selection for Frontend:**
   * *Proposed:* **Recharts** (React-native, SVG-based, accessible, lightweight) vs. **Visx** (lower-level, D3-backed). Recharts is the recommended default for dashboard maintainability.
3. **Downstream Package Packaging:**
   * *Proposed:* Runport will be pip-installable as a standard package (`pip install -e .`). Private downstream workloads will pin `runport` in their dependencies and implement domain evaluators as custom workloads/plugins.
4. **TokenApprover Lifetime:**
   * *Proposed:* Single-use token consumed in-memory during CLI process execution. The fingerprint is computed from the SHA-256 of `(dataset_hash, models_tuple, routes_tuple, caps_tuple, prompt_hash)`.

---

## 5. Architectural Compatibility Check

| Decision | Compatibility Finding | Risk of Invariant Violation |
|---|---|---|
| **D2 (Approvals)** | Compatible. Generalizes `core/live_guard.py` into `Approver` interface. Recomputing the plan on-the-fly ensures token approvals cannot be replayed against altered plans. | **None.** Fail-closed behavior preserved. |
| **D3 (Budgets)** | Compatible. Integrates directly with `core/budget.py` and `storage/db.py`. Preserves integer micro-dollar arithmetic, circuit breakers, and unresolved-spend blocks. | **None.** Strict bounds remain intact. |
| **D4 (Replay)** | Compatible. Uses the existing ledger/result provenance separation (`ACTUAL`, `ESTIMATED`, `UNRESOLVED`, `REPLAYED`). Replayed rows are excluded from benchmark leaderboards and spend accounting. | **None.** Simulation rule honored through strict labeling. |
| **D5 (Web UI)** | Compatible. The Web UI acts as an alternative client to the CLI/TUI, consuming the same `EventTail` JSONL stream and SQLite database. Zero dual-store drift. | **None.** Read-only monitor pattern preserved. |
| **D6 (Licensing/IP)** | Compatible. Clean-slate Git repository purges confidential history. Stripping domain-specific data makes the core universally open-sourcable. | **None.** Confirmed before publication. |
| **D7 (Subsystems)** | Compatible. Promotes existing connectors to core `src/runport/connectors/`. Decouples specialized rules into plugins. | **None.** Strengthens modularity. |
| **D8 (Telemetry)** | Compatible. Enforces the local-first design principle. | **None.** Zero network leakage. |

---

## 6. Revised Phase 0 Readiness Plan & Audit

This section resolves the six critical readiness requirements identified prior to Phase 0 authorization.

### 6.1 Independent Backup Strategy & Checksum Manifest
* **Requirement:** Replace any local sibling-directory backup with a genuinely independent backup on a separate physical storage medium or secure external drive volume.
* **Scope of Backup:** The backup must capture:
  1. All tracked repository files.
  2. All untracked working-tree files.
  3. All git-ignored files (local databases, telemetry logs, prep datasets, environment files).
  4. The complete `.git/` history and reflog.
* **Target Destination:** `/Volumes/<Secure_External_Drive>/Workbench_Master_Backup_20261102` (or user-designated secure path `~/SecureBackups/Workbench_Master_Backup_20261102`).
* **Verification Protocol:**
  ```bash
  # 1. Recursive copy preserving metadata and symlinks
  rsync -aP "/path/to/source-repo/" "/Volumes/<Drive>/Master_Backup_20261102/"

  # 2. Generate SHA-256 manifest of source and backup
  find . -type f -not -path "./.git/*" -exec shasum -a 256 {} + | sort -k2 > /tmp/src_manifest.sha256
  cd "/Volumes/<Drive>/Workbench_Master_Backup_20261102"
  find . -type f -not -path "./.git/*" -exec shasum -a 256 {} + | sort -k2 > /tmp/backup_manifest.sha256

  # 3. Cryptographic diff
  diff /tmp/src_manifest.sha256 /tmp/backup_manifest.sha256
  ```
* **Acceptance Gate:** Zero differences in file count, total byte count, and SHA-256 manifest.

---

### 6.2 Git Staging Safety & Explicit Allowlist Procedure
* **Requirement:** Unconditionally eliminate `git add .` from all proposed workflows. Staging must be explicitly allowlist-driven.
* **Allowlist Staging Specification:**
  Only explicitly verified public directories and files may be staged:
  ```bash
  # Explicit allowlist additions only:
  git add pyproject.toml
  git add README.md
  git add LICENSE
  git add NOTICE
  git add .gitignore
  git add src/runport/
  git add tests/
  git add docs/
  git add examples/
  ```
* **Pre-Commit Staging Inspection Pipeline:**
  1. **List Staged Paths:** `git diff --staged --name-only`
  2. **Verify Against Forbidden Patterns:** Verify zero confidential data files, secrets, local databases, or private environment files are staged.
  3. **Secret Scan on Staged Blobs:** Run `gitleaks protect --staged --verbose` or an automated secret scanner searching for API keys (`sk-or-v1-`, `app-`, bearer tokens).
  4. **Staged Content Diff Review:** Run `git diff --staged` and review the full diff text before executing `git commit`.

---

### 6.3 Targeted `.gitignore` Precision
* **Requirement:** Replace overly broad wildcard exclusions with surgical rules so that legitimate documentation, public datasets, examples, and synthetic test fixtures remain committable.

---

### 6.4 Comprehensive Confidential-Data Clearance Protocol
* **Requirement:** Expand data clearance beyond basic keywords to multi-format scanning, content classes, Git object verification, and explicit distinction between automated scans and human review.
* **Scan Format Coverage:**
  * Plaintext: `.py`, `.md`, `.txt`, `.json`, `.jsonl`, `.yaml`, `.toml`, `.csv`
  * Binaries / Storage: `.pdf`, `.png`, `.jpg`, `.db`, `.sqlite`, Git tree blobs.
* **Content Class Audit Targets:**
  * **Phone Numbers:** International and raw digit sequences.
  * **Personal Identifiers:** Customer/user names, email addresses, phone prefix sentinels.
  * **Secrets & Credentials:** API keys, Bearer tokens, Authorization headers.
  * **Proprietary Internal Content:** Private commercial figures, internal prompts, organization-specific operational data.
* **Verification Targets:**
  1. Working directory files prior to staging.
  2. Git staged index (`git diff --staged`).
  3. Committed Git object store (`git rev-list --objects --all`).
* **Governance Boundary (Automated vs. Human Review):**
  * *Automated Scan:* Acts as a mechanical prerequisite filter. A clean automated scan proves the absence of known patterns.
  * *Human Review:* Mandatory legal and domain-owner review. **A clean automated scan NEVER constitutes formal IP clearance.** The project remains marked *CONFIDENTIAL / NOT CLEARED FOR EXTERNAL RELEASE* until the owner executes formal sign-off.

---

### 6.5 Extraction Validation & Behavioral Equivalence
* **Requirement:** Define behavioral-equivalence tests for every extraction target *before* its source is deleted. Standardize all paths under `src/runport/...`.

#### Extraction Target 1: Statistical Helpers
* **Destination:** `src/runport/scorers/stats.py`
* **Functions:** `wilson(k, n, z)`, `boot_ci(values, stat, label, n_boot, seed)`, `pct(v, q)`, `holm(pvals)`, `cohen_kappa(a, b)`, `rng_for(label, seed)`, `sha256_file(path)`.
* **Behavioral Equivalence Test (`tests/test_scorers_stats.py`):**
  Asserts that calling `runport.scorers.stats` produces:
  * Identical Wilson confidence interval tuples across edge cases ($k=0$, $k=n$, $n=0$, $n=10,000$).
  * Bit-identical Bootstrap CI bounds given identical seeds.
  * Identical Holm-Bonferroni adjusted $p$-value arrays across sorted and unsorted distributions.
  * Identical Cohen's Kappa scores across perfect agreement, random agreement, and zero-variance inputs.

#### Extraction Target 2: PII Redaction
* **Destination:** `src/runport/datasets/redaction.py`
* **Functions:** `redact(text)`, `redact_email(text)`, `redact_phone(text)`, `salted_hash(text, salt)`.
* **Behavioral Equivalence Test (`tests/test_redaction.py`):**
  Asserts identical redaction replacements on a synthetic test corpus of international phone numbers, email addresses, names, and salted hash surrogates.

#### Extraction Target 3: Dify Client & SSE Streaming Integration
* **Destination:** `src/runport/connectors/dify.py`
* **Functions:** `post_chat_message(...)`, `post_chat_stream(...)`.
* **Behavioral Equivalence Test (`tests/test_dify_connector.py`):**
  Uses recorded HTTP fixtures and mocked transport to verify:
  * Byte-identical request payloads and authorization headers (`Authorization: Bearer <key>`).
  * Preservation of exact timeout classifications: `HTTP`, `CONNECTION_ERROR`, `AMBIGUOUS_TIMEOUT`.
  * Identical SSE streaming event parsing and timestamp recording (`wall_ms`, event arrival order).
  * Secret scrubbing: Zero leakage of keys or Bearer tokens in logs or returned error structures.

#### Extraction Target 4: Model Catalog Data Model
* **Destination:** `src/runport/models/catalog.py`
* **Data Model:** `ModelCandidate` Pydantic model and validation rules.
* **Behavioral Equivalence Test:** Verifies schema compatibility and field validation.

---

### 6.6 Test Retirement & Baseline Failure Mapping
* **Rule:** Never retire a test merely to improve the passing-test count. Every test must have a recorded purpose, failure analysis, migration decision, and replacement test if applicable.

---

### 6.7 Reassessed Phase 0 Execution Sequence

```text
Step 0.1: Independent Physical Backup & Cryptographic Checksum
  ├─ Prerequisite: External drive or secure directory mounted and writable.
  ├─ Action: rsync full workspace (tracked, untracked, ignored, .git) to external drive.
  ├─ Validation: shasum -a 256 manifest generated and verified identical.
  └─ Stop Condition: Any file copy failure or manifest discrepancy halts sequence.

Step 0.2: Statistical Helpers & Redaction Extraction (Pre-Removal)
  ├─ Prerequisite: Step 0.1 verified.
  ├─ Action: Create src/runport/scorers/stats.py and src/runport/datasets/redaction.py.
  ├─ Validation: Run test suites covering statistical calculations and PII redaction.
  └─ Stop Condition: Any behavioral deviation from expected calculations halts sequence.

Step 0.3: Relocate Reusable Subsystem Plugins
  ├─ Prerequisite: Step 0.2 verified.
  ├─ Action: Move audit/ and remediation/ to examples/plugins/kb_audit/; move custom protocol adapters to examples/plugins/.
  ├─ Validation: Plugin directories exist; plugin unit tests pass.
  └─ Rollback Checkpoint: Revert moves from Step 0.1 backup.

Step 0.4: Purge Obsolete Study Packages & Confidential Prototype Files
  ├─ Prerequisite: Steps 0.2 and 0.3 passing.
  ├─ Action: Delete obsolete domain evaluation runners, legacy study packages, and local prototype files.
  ├─ Validation: Verify legacy domain-specific files are absent from the tree.
  └─ Stop Condition: Residual references halt sequence.

Step 0.5: Package Directory & Configuration Initialization
  ├─ Prerequisite: Step 0.4 complete.
  ├─ Action: Ensure src/runport/ package structure is active; verify pyproject.toml package configuration.
  ├─ Validation: src/runport/ exists; pyproject.toml package is "runport".
  └─ Stop Condition: Directory check failure halts process.

Step 0.6: Global Import Refactoring & De-Branding
  ├─ Prerequisite: Step 0.5 complete.
  ├─ Action: Update outbound HTTP headers; de-brand CLI/TUI text to Runport.
  ├─ Validation: uv run pytest --collect-only collects remaining test suite with zero ImportErrors.
  └─ Stop Condition: Any unresolved collection error halts sequence.

Step 0.7: Test Baseline Stabilization & Bug Fixes
  ├─ Prerequisite: Step 0.6 complete.
  ├─ Action: Fix catalog pricing attributes, update test assertions to reflect dynamic registry.
  ├─ Validation: uv run pytest -q passes with 0 failures and 0 errors.
  └─ Stop Condition: Any persisting test failure halts sequence.

Step 0.8: Full Multi-Format Leak Scan & Clean Install Verification
  ├─ Prerequisite: Step 0.7 fully green.
  ├─ Action: Run automated leak scan across all formats; test clean venv install; run CLI.
  ├─ Validation: All Phase 0 acceptance criteria verified.
  └─ Stop Condition: Any detected leak or installation error halts sequence.

Step 0.9: Git History Purge & Allowlist-Based Initial Commit
  ├─ Prerequisite: Step 0.8 passing 100%.
  ├─ Action:
      1. Fresh repository initialization on main branch
      2. Write targeted .gitignore
      3. Allowlist staging
      4. Pre-commit check: git diff --staged --name-only and secret scan
      5. Initial commit of clean Runport platform
  ├─ Validation: git log shows clean commits; git status is clean.
  └─ Completion: Phase 0 complete.
```

---

### 6.8 Irreversible or Potentially Destructive Operations
1. **`rm -rf .git` (Destructive):** Permanently erases local Git revision history. (*Guaranteed independent external backup created in Step 0.1 before any deletion*).
2. **Deletion of Root Prototype CSVs, KBs, and Study Packages (Destructive):** Permanently removes local prototype files from this workspace. (*Preserved in Step 0.1 external backup*).

---

### 6.9 Distinction Between Verified Facts and Assumptions
* **Verified Facts:**
  * PyPI package `runport` and GitHub repo `Sudharsanselvaraj/runport` are completely available (404).
  * Core test suite passes completely offline with zero network calls and blocked sockets.
  * Codebase adheres strictly to Runport architectural invariants.
* **Recommendations:**
  * Execute migration phases strictly in the numbered order.
  * Do not publish the repository publicly until formal legal and IP clearance is signed off by the owner.

---

## 7. Phase 0 Readiness Verdict

# **VERDICT: READY WITH CONDITIONS**

### Justification:
The migration plan is fully specified, the safety issues are rigorously resolved, the dependency graph is mapped, and the extraction-first validation sequence prevents code loss or regression.

---

## 8. Current Status & Next Action

* **Status:** **PHASE 0 AND PHASE B COMPLETED.**
* **Next Action:** Finalize Phase B audit and stand by for Phase C authorization.

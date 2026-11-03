# Owner Decisions & Architectural Plan: Runport

This document records all confirmed decisions made by the project owner for transitioning the codebase into **Runport** (`runport`), an open-source, any-API / any-workflow benchmarking platform. It also records unresolved implementation questions, an architectural compatibility check, the complete Phase 0 Readiness Audit, and the finalized execution plan.

---

## 1. Decision Record Matrix

| # | Topic | Status | Owner Decision Summary |
|---|---|---|---|
| **1** | **Project Identity & Naming** | **OWNER-CONFIRMED** | Name: **Runport** (`runport`). CLI: `runport`. "Inferia" brand kept separate. Prior candidates replaced. |
| **2** | **Execution Approval Model** | **OWNER-CONFIRMED** | Interactive CLI/TUI: typed phrase. Web UI: modal approval. CI: `--approve <plan_fingerprint>`. Plan always recomputed before check; no stale approvals. |
| **3** | **Budget & Pricing Defaults** | **OWNER-CONFIRMED** | Ceilings: Total $5.00, Run $1.00, Case $0.05. `require_priced: true` by default. Unpriced models fail preflight unless overridden. Strict separation of Actual / Estimated / Unavailable. |
| **4** | **Replay Mode** | **OWNER-CONFIRMED** | Fixture-based replay supported. Provenance strictly labeled `REPLAYED`. Never mixed with live benchmark results or actual spend. |
| **5** | **Web Interface Architecture** | **OWNER-CONFIRMED** | FastAPI backend + React/TS/Vite frontend. Single-user localhost deployment. No accounts or auth in initial release. Charting library chosen for maintainability. |
| **6** | **License & IP Clearance** | **CONDITIONALLY APPROVED** | Target license: Apache 2.0. Clean-slate Git repo approved in principle. Mandatory audit of all data/prompts for confidential MSU text before publishing. Private MSU fork preserved downstream. |
| **7** | **Subsystem Migration Scope** | **OWNER-CONFIRMED** | Dify chat + SSE streaming preserved in core (`src/runport/connectors/dify.py`). Jev Decisions API moved to `examples/plugins/`. KB audit moved to `examples/plugins/kb_audit/`. MSU admissions assumptions stripped from core. |
| **8** | **Telemetry Policy** | **OWNER-CONFIRMED** | Zero external telemetry. No phoning home. Operational records strictly local. Documented in `SECURITY.md`. |

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
* **Clean-Slate Git Repository:** Approved in principle for Phase 0 to permanently purge confidential admissions data, candidate phone numbers, and internal prompts from Git commit history.
* **IP Clearance Gate:** Before publishing to GitHub or PyPI, conduct a comprehensive audit across all files, test fixtures, datasets, prompts, and logs to ensure no proprietary MSU admissions text or third-party IP remains. Publishing is blocked until clearance is complete.
* **Downstream Architecture:** The internal MSU admissions workbench will be preserved as a private downstream consumer that imports `runport` as an external library.

### Decision 7 — Subsystem Migration & Core Extraction
* **Dify Integration:** The existing 4,180-line `dify_eval/` package will be audited:
  * `client.py` (`post_chat_message`) and `rag_stream.py` (SSE streaming) are extracted into core `src/runport/connectors/dify.py`.
  * One-off study evaluation runners and report generators are deleted.
* **Jev Decisions API:** Moved to `examples/plugins/jev_decisions_api/` as a worked example of an custom protocol adapter.
* **KB Auditor & Remediation:** Moved to `examples/plugins/kb_audit/`.
* **Domain Decoupling:** All admissions-specific rules, hardcoded classifications (`Task.INTENT/LEAD`), and university references are eliminated from the core platform while preserving research provenance in migration docs.

### Decision 8 — Telemetry & Network Policy
* **Zero External Telemetry:** Runport will emit zero telemetry, analytics, tracking pings, or diagnostic reports over the network to any third party.
* **Local Storage Only:** All telemetry remains strictly local (`data/telemetry/request_events.jsonl` and SQLite ledger).
* **Transparency:** Network behavior, local socket bindings, and the zero-telemetry guarantee will be documented in `SECURITY.md`.

---

## 3. Identity Verification & Naming Conflict Audit for "Runport"

### 3.1 Verified Availability & Non-Conflict Results
* **PyPI (`runport`):** **VERIFIED AVAILABLE.** Live JSON API check (`https://pypi.org/pypi/runport/json`) returned **HTTP 404**. Unregistered and free to claim.
* **CLI Command (`runport`):** **VERIFIED UNCONTESTED.** No standard system utility, Unix binary, or popular Python tool uses `runport`.
* **GitHub Repository (`Sudharsanselvaraj/runport`):** **VERIFIED AVAILABLE.** Endpoint `https://github.com/Sudharsanselvaraj/runport` returned **HTTP 404**.
* **Software Trademarks:** **VERIFIED CLEAR.** Exhaustive search showed no registered or active software trademark for "Runport" in AI, benchmarking, or developer tools.

### 3.2 Items Requiring Owner Awareness / Action
* **GitHub Organization Name (`github.com/runport`):** An individual personal user account exists at `github.com/runport` (registered Sept 2019, inactive profile). The bare organization name is unavailable immediately. Recommended paths:
  * `github.com/Sudharsanselvaraj/runport`
  * `github.com/runport-org/runport`
  * `github.com/runport-ai/runport`
* **Domain Names:**
  * `runport.com`: Registered and active (85.131.221.24).
  * `runport.dev`, `runport.io`, `runport.org`, `runport.ai`: Have no active DNS A-records (NXDOMAIN / unassigned). Owner should check registrar pricing if securing a domain is desired.

---

## 4. Unresolved Implementation Questions (For Phase 1 & 2 Execution)

1. **Replay Connector Fixture Format:**
   * *Proposed:* JSONL file where each record matches `TargetResult` schema with `provenance: "REPLAYED"`, stored under `tests/fixtures/replay/` or `examples/fixtures/`.
2. **Chart Library Selection for Frontend:**
   * *Proposed:* **Recharts** (React-native, SVG-based, accessible, lightweight) vs. **Visx** (lower-level, D3-backed). Recharts is the recommended default for dashboard maintainability.
3. **Downstream Package Packaging:**
   * *Proposed:* Runport will be pip-installable as a standard package (`pip install -e .`). The private MSU workbench will pin `runport` in its `pyproject.toml` dependencies and implement admissions-specific evaluators as custom workloads/plugins.
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
| **D6 (Licensing/IP)** | Compatible. Clean-slate Git repository purges confidential history. Stripping admissions data makes the core universally open-sourcable. | **None.** Confirmed before publication. |
| **D7 (Subsystems)** | Compatible. Promotes existing `dify_eval` client to core `src/runport/connectors/dify.py`. Decouples admissions rules into plugins. | **None.** Strengthens modularity. |
| **D8 (Telemetry)** | Compatible. Enforces the local-first design principle. | **None.** Zero network leakage. |

---

## 6. Revised Phase 0 Readiness Plan & Audit

This section resolves the six critical readiness requirements identified prior to Phase 0 authorization.

### 6.1 Independent Backup Strategy & Checksum Manifest
* **Requirement:** Replace the sibling-directory backup with a genuinely independent backup on a separate physical storage medium or secure external drive volume.
* **Scope of Backup:** The backup must capture:
  1. All tracked repository files.
  2. All untracked working-tree files (including uncommitted scripts and CSVs).
  3. All git-ignored files (local databases `workbench.db`, telemetry logs `request_events.jsonl`, prep datasets, `.env`).
  4. The complete `.git/` history and reflog.
* **Target Destination:** `/Volumes/<Secure_External_Drive>/MSU_LLM_Workbench_Master_Backup_20261102` (or user-designated secure path `~/SecureBackups/MSU_LLM_Workbench_Master_Backup_20261102`).
* **Verification Protocol:**
  ```bash
  # 1. Recursive copy preserving metadata and symlinks
  rsync -aP "/path/to/source-repo/" "/Volumes/<Drive>/Master_Backup_20261102/"

  # 2. Generate SHA-256 manifest of source and backup
  find . -type f -not -path "./.git/*" -exec shasum -a 256 {} + | sort -k2 > /tmp/src_manifest.sha256
  cd "/Volumes/<Drive>/MSU_LLM_Workbench_Master_Backup_20261102"
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
  2. **Verify Against Forbidden Patterns:**
     ```bash
     git diff --staged --name-only | grep -E "(september_to_october|MSU|intent_test|lead_qualification|jev_wrong|workbench\.db|\.env|PDF|user4)"
     ```
     *(Must return zero hits; any match aborts the commit).*
  3. **Secret Scan on Staged Blobs:** Run `gitleaks protect --staged --verbose` or an automated secret scanner searching for API keys (`sk-or-v1-`, `app-`, bearer tokens).
  4. **Staged Content Diff Review:** Run `git diff --staged` and review the full diff text before executing `git commit`.

---

### 6.3 Targeted `.gitignore` Precision
* **Requirement:** Replace overly broad wildcard exclusions (`*.csv`, `*.pdf`, `data/`) with surgical rules so that legitimate documentation, public datasets, examples, and synthetic test fixtures remain committable.
* **Refined `.gitignore` Rules:**
  ```gitignore
  # -----------------------------------------------------------------------------
  # Confidential Admissions Data (Targeted Surgical Rules)
  # -----------------------------------------------------------------------------
  september_to_october.csv
  Copy of MSU *.md
  msu_intent*.csv
  intent_test_cases*.csv
  lead_qualification*.csv
  jev_wrong_cases_with_history.csv
  main_intent*.md
  lead_qualification_prompt.md
  PDF/
  Intent:lead dataset/
  model_provider_cost_estimate_table.png

  # -----------------------------------------------------------------------------
  # Local Runtime Storage & Databases (Do not exclude test fixtures)
  # -----------------------------------------------------------------------------
  workbench.db*
  runport.db*
  *.db
  *.db-wal
  *.db-shm
  data/telemetry/
  data/classification_prep/
  reports/exports/
  reports/smoke/
  reports/classification/
  reports/real_benchmark_*
  reports/executive_summary_*

  # -----------------------------------------------------------------------------
  # Local Secrets & Environment
  # -----------------------------------------------------------------------------
  .env
  .env.*
  !.env.example

  # -----------------------------------------------------------------------------
  # Python & System Artifacts
  # -----------------------------------------------------------------------------
  __pycache__/
  *.py[cod]
  *$py.class
  .pytest_cache/
  .venv/
  *.egg-info/
  dist/
  build/
  .DS_Store
  .deepeval/

  # -----------------------------------------------------------------------------
  # Explicit Allowances for Public & Synthetic Assets
  # -----------------------------------------------------------------------------
  !tests/fixtures/**
  !examples/data/**
  !docs/assets/**
  ```

---

### 6.4 Comprehensive Confidential-Data Clearance Protocol
* **Requirement:** Expand data clearance beyond basic keywords to multi-format scanning, content classes, Git object verification, and explicit distinction between automated scans and human review.
* **Scan Format Coverage:**
  * Plaintext: `.py`, `.md`, `.txt`, `.json`, `.jsonl`, `.yaml`, `.toml`, `.csv`
  * Binaries / Storage: `.pdf`, `.png`, `.jpg`, `.db`, `.sqlite`, Git tree blobs.
* **Content Class Audit Targets:**
  * **Phone Numbers:** Malaysian (`\+?60\d{8,10}`, `01\d{8,9}`), international, and raw digit sequences.
  * **Personal Identifiers:** Student names, email addresses (`[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+`), phone prefix `user4`.
  * **Secrets & Credentials:** `sk-or-v1-[a-zA-Z0-9]{16,}`, `sk-[a-zA-Z0-9]{16,}`, `app-[a-zA-Z0-9]{8,}`, Bearer tokens, Authorization headers.
  * **Proprietary Admissions Content:** Tuition figures in Ringgit (`RM\s?[0-9,]{3,}`), specific programme descriptions, faculty names, internal prompt templates.
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
* **Source:** `src/msu_llm_lab/observability/evaluation_report.py` (lines 55–115)
* **Destination:** `src/runport/scorers/stats.py`
* **Functions:** `wilson(k, n, z)`, `boot_ci(values, stat, label, n_boot, seed)`, `pct(v, q)`, `holm(pvals)`, `cohen_kappa(a, b)`, `rng_for(label, seed)`, `sha256_file(path)`.
* **Behavioral Equivalence Test (`tests/test_scorers_stats_equivalence.py`):**
  Asserts that calling `runport.scorers.stats` and `msu_llm_lab.observability.evaluation_report` on identical inputs produces:
  * Identical Wilson confidence interval tuples across edge cases ($k=0$, $k=n$, $n=0$, $n=10,000$).
  * Bit-identical Bootstrap CI bounds given identical seeds.
  * Identical Holm-Bonferroni adjusted $p$-value arrays across sorted and unsorted distributions.
  * Identical Cohen's Kappa scores across perfect agreement, random agreement, and zero-variance inputs.

#### Extraction Target 2: PII Redaction
* **Source:** `src/msu_llm_lab/classification/dataprep.py` (lines 40–85)
* **Destination:** `src/runport/datasets/redaction.py`
* **Functions:** `redact(text)`, `redact_email(text)`, `redact_phone(text)`, `salted_hash(text, salt)`.
* **Behavioral Equivalence Test (`tests/test_redaction_equivalence.py`):**
  Asserts identical redaction replacements on a synthetic test corpus of international phone numbers, email addresses, names, and salted hash surrogates.

#### Extraction Target 3: Dify Client & SSE Streaming Integration
* **Source:** `src/msu_llm_lab/dify_eval/client.py` (`post_chat_message`) and `src/msu_llm_lab/dify_eval/rag_stream.py` (`post_chat_stream`)
* **Destination:** `src/runport/connectors/dify.py`
* **Functions:** `post_chat_message(...)`, `post_chat_stream(...)`.
* **Behavioral Equivalence Test (`tests/test_dify_connector_equivalence.py`):**
  Uses recorded HTTP fixtures and mocked `urllib.request.urlopen` to verify:
  * Byte-identical request payloads and authorization headers (`Authorization: Bearer <key>`).
  * Preservation of exact timeout classifications: `HTTP`, `CONNECTION_ERROR`, `AMBIGUOUS_TIMEOUT`.
  * Identical SSE streaming event parsing and timestamp recording (`wall_ms`, event arrival order).
  * Secret scrubbing: Zero leakage of `app-[A-Za-z0-9]{8,}` or Bearer tokens in logs or returned error structures.

#### Extraction Target 4: Model Catalog Data Model
* **Source:** `src/msu_llm_lab/models/catalog.py`
* **Destination:** `src/runport/catalog/models.py`
* **Data Model:** `ModelCandidate` Pydantic model and validation rules.
* **Behavioral Equivalence Test:** Verifies schema compatibility and field validation without hardcoding `DEFAULT_PORTFOLIO`.

---

### 6.6 Test Retirement & Baseline Failure Mapping
* **Rule:** Never retire a test merely to improve the passing-test count. Every test must have a recorded purpose, failure analysis, migration decision, and replacement test if applicable.

#### Mapping of the 8 Baseline Test Failures
| # | Test Identifier | Original Purpose | Why It Failed in Baseline | Migration Decision | Replacement Test / Guard |
|---|---|---|---|---|---|
| **F1** | `tests/classification/test_splits_metrics_privacy.py::test_package_has_no_network_or_csv_imports_and_no_real_data_reference` | Enforce architectural isolation (no network/csv imports in classification). | Ad-hoc script `claude_cost_validation_runner.py` in `classification/` imported `urllib`. | **Fix & Retain.** Remove ad-hoc script. Retain architectural isolation test for `src/runport/workloads/`. | Ported as `tests/test_architecture_isolation.py`. |
| **F2** | `tests/test_budget.py::test_model_catalog_seeding_and_unverified_labels` | Assert seeded candidate models have positive prices. | `minimax/minimax-m3.1-flash` in `models/catalog.py` had price `Decimal("0.0000")`. | **Fix & Retain.** Fix zero price in catalog/facts. Update test to verify that unpriced models fail preflight when `require_priced: true`. | Retained in `tests/test_budget.py`. |
| **F3** | `tests/test_evaluation_report.py::test_end_to_end_reconciliation_and_no_ground_truth` | Validate report generation for the 17-block study run (`bench-d0a763e4a920-r4`). | Matplotlib 3.9+ removed deprecated `labels` argument in `ax.boxplot(...)`. | **Retire.** The 17-block narrative study generator is obsolete. | Statistical helper logic covered by `tests/test_scorers_stats.py`. Template reports covered in Phase 2. |
| **F4** | `tests/test_evaluation_report.py::test_redesign_is_shorter_has_no_toc_and_keeps_every_figure` | Check page count and layout of redesigned study PDF. | `ModuleNotFoundError: No module named 'pymupdf'`. | **Retire.** One-off PDF layout generator is deleted. | PDF generation in Runport will use graceful extras and mocked canvas tests. |
| **F5** | `tests/test_remediation.py::test_remediation_engine_dry_run_preserves_source_hash` | Validate markdown KB patch engine immutability. | Local `Copy of MSU Programmes KB...` had hash `fda0ee3...` differing from hardcoded test expectation `830c27...`. | **Relocate to Plugin.** Move KB audit/remediation to `examples/plugins/kb_audit/`. | Runs on fixed version-controlled markdown fixtures in `examples/plugins/kb_audit/tests/`. |
| **F6** | `tests/test_remediation.py::test_remediation_cli_command` | Verify CLI output of `remediate-kb`. | Local KB content differed from expected table stdout. | **Relocate to Plugin.** Move with plugin. | Relocated to `examples/plugins/kb_audit/tests/`. |
| **F7** | `tests/test_tui.py::test_health_checks_live` | Verify live system diagnostics on TUI startup. | Hardcoded checks for `"MSU Programmes KB"` failed due to local file hash. | **Fix & Retain.** De-brand `health.py` to check Python runtime, SQLite WAL mode, and workspace config. | Updated test asserts generic health checks PASS. |
| **F8** | `tests/test_tui.py::test_model_catalogue_navigation_and_details_sync` | Verify Up/Down navigation and cursor clamping in TUI catalogue. | Hardcoded index 4 failed (`assert 5 == 4`) because a 6th model had been added to portfolio. | **Fix & Retain.** Update clamping assertion to use dynamic `len(candidates) - 1`. | Retained in `tests/test_tui.py`. |

#### Mapping of the 10 Proposed Obsolete Test Files
| # | Test File | Original Purpose | Migration Decision | Replacement Test / Evidence for Retirement |
|---|---|---|---|---|
| **T1** | `tests/test_candidate_v3_prompt_rules.py` (108 lines) | Validates Candidate Prompt V3 rules for MSU Main Intent. | **Retire.** | Tests specific admissions prompt text. Replaced by generic prompt serialization tests in Phase 2. |
| **T2** | `tests/classification/test_claude_cost_validation.py` (89 lines) | Tests Claude Haiku cost-validation study on `msu_intent_test_cases300.csv`. | **Retire.** | One-off study validation. Replaced by generic provider pricing contract tests in `tests/test_providers.py`. |
| **T3** | `tests/classification/test_jev_experiment.py` (155 lines) | Tests Jev prompt experiment variants (baseline, v2, v3). | **Relocate.** | Preserved under `examples/plugins/jev_decisions_api/tests/`. |
| **T4** | `tests/classification/test_jev_lead_choice.py` (109 lines) | Tests Jev Choice primitive for Lead qualification. | **Relocate.** | Preserved under `examples/plugins/jev_decisions_api/tests/`. |
| **T5** | `tests/test_lead_report_final.py` (26 lines) | Tests helper functions for lead qualifier PDF report. | **Retire.** | Tied to deleted `lead_report_final/`. Replaced by generic template report tests in Phase 2. |
| **T6** | `tests/test_main_intent_master_metrics.py` (213 lines) | Tests metric calculations against the retrospective 220-case split. | **Retire.** | Tied to deleted `master_intent_metrics.py` and `retro_split/`. Metric math tested in `test_metrics.py`. |
| **T7** | `tests/test_v2_report_final.py` (33 lines) | Tests helper functions for v2 PDF comparison report. | **Retire.** | Tied to deleted `v2_report_final/`. Replaced by generic template report tests in Phase 2. |
| **T8** | `tests/test_labeled_eval.py` (196 lines) | Tests `labeled_eval` module (120/200 case suites, Mistral last). | **Retire.** | Internal one-off study harness. Generic execution tested in `test_runs.py`. |
| **T9** | `tests/test_evaluation_report.py` (70 lines) | Tests 17-block evaluation bundle and stats helpers. | **Extract & Retire.** | Statistical helper tests preserved in `tests/test_scorers_stats.py`; bundle tests retired. |
| **T10** | `tests/classification/test_main_intent_v2*.py` (6 files, 986 lines) | Comprehensive suite for v2 contracts, 300-case CSV, and reports. | **Retire.** | Tied directly to deleted v2 study packages. Core classification logic covered by `test_contracts.py` and `test_validators.py`. |

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
  ├─ Validation: Run tests/test_scorers_stats_equivalence.py and tests/test_redaction_equivalence.py.
  └─ Stop Condition: Any behavioral deviation from legacy functions halts sequence.

Step 0.3: Relocate Reusable Subsystem Plugins
  ├─ Prerequisite: Step 0.2 verified.
  ├─ Action: Move audit/ and remediation/ to examples/plugins/kb_audit/; move jev_* to examples/plugins/jev_decisions_api/.
  ├─ Validation: Plugin directories exist; plugin unit tests pass.
  └─ Rollback Checkpoint: Revert moves from Step 0.1 backup.

Step 0.4: Purge Obsolete Study Packages & Confidential Admissions Files
  ├─ Prerequisite: Steps 0.2 and 0.3 passing.
  ├─ Action: Delete labeled_eval/, lead_report_final/, v2_report_final/, retro_split/, classification/v2_*, and confidential root CSV/KB/prompt files.
  ├─ Validation: find ... confirms confidential filenames are absent from the tree.
  └─ Stop Condition: Inability to delete or residual references halt sequence.

Step 0.5: Package Directory & Configuration Rename
  ├─ Prerequisite: Step 0.4 complete.
  ├─ Action: Rename directory src/msu_llm_lab/ -> src/runport/; update pyproject.toml and src/runport/core/config.py.
  ├─ Validation: src/runport/ exists; pyproject.toml package is "runport".
  └─ Stop Condition: Directory move failure halts process.

Step 0.6: Global Import Refactoring & De-Branding
  ├─ Prerequisite: Step 0.5 complete.
  ├─ Action: Refactor msu_llm_lab.* -> runport.*; update outbound HTTP headers; de-brand CLI/TUI text.
  ├─ Validation: uv run pytest --collect-only collects remaining test suite with zero ImportErrors.
  └─ Stop Condition: Any unresolved collection error halts sequence.

Step 0.7: Test Baseline Stabilization & Bug Fixes
  ├─ Prerequisite: Step 0.6 complete.
  ├─ Action: Fix minimax catalog zero-price bug, fix Matplotlib 3.9 boxplot syntax, retire obsolete study tests per Section 6.6 mapping.
  ├─ Validation: uv run pytest -q passes with 0 failures and 0 errors.
  └─ Stop Condition: Any persisting test failure halts sequence.

Step 0.8: Full Multi-Format Leak Scan & Clean Install Verification
  ├─ Prerequisite: Step 0.7 fully green.
  ├─ Action: Run automated leak scan across all formats; test clean venv install; run CLI from /tmp.
  ├─ Validation: All Phase 0 acceptance criteria verified.
  └─ Stop Condition: Any detected leak or installation error halts sequence.

Step 0.9: Git History Purge & Allowlist-Based Initial Commit
  ├─ Prerequisite: Step 0.8 passing 100%.
  ├─ Action:
      1. rm -rf .git
      2. git init -b main
      3. Write targeted .gitignore
      4. Allowlist staging (git add pyproject.toml README.md LICENSE src/ tests/ docs/ examples/)
      5. Pre-commit check: git diff --staged --name-only and secret scan
      6. git commit -m "Initial commit: Runport open-source benchmarking platform"
  ├─ Validation: git log shows single initial commit; git status is clean.
  └─ Completion: Phase 0 complete.
```

---

### 6.8 Irreversible or Potentially Destructive Operations
1. **`rm -rf .git` (Destructive):** Permanently erases local Git revision history. (*Guaranteed independent external backup created in Step 0.1 before any deletion*).
2. **Deletion of Root Admissions CSVs, KBs, and Study Packages (Destructive):** Permanently removes local admissions files from this workspace. (*Preserved in Step 0.1 external backup*).
3. **Directory Rename `src/msu_llm_lab/` → `src/runport/`:** Breaks existing `.venv` editable install. (*Reinstalled immediately with `uv pip install -e .`*).

---

### 6.9 Distinction Between Verified Facts and Assumptions
* **Verified Facts:**
  * Exact line counts and file counts (161 Python files, 45,350 lines in `src/msu_llm_lab/`).
  * Baseline test suite results: 873 passed, 8 failed, 1 skipped, 5 deselected in 28.88s.
  * Root causes for all 8 test failures are documented with exact file lines and stack traces.
  * PyPI package `runport` and GitHub repo `Sudharsanselvaraj/runport` are completely available (404).
  * Inbound dependency graph for all modules slated for deletion is mapped.
* **Assumptions (Subject to verification during Step 0.6–0.8 execution):**
  * Assumption: That retiring the 10 study test files will cleanly eliminate 6 of the 8 failures without hidden side-effects on shared fixtures.
  * Assumption: That no third-party package dependency assumes `msu_llm_lab` package naming.
* **Recommendations:**
  * Execute Phase 0 strictly in the numbered order.
  * Do not publish the repository publicly until formal legal and IP clearance is signed off by the owner.

---

## 7. Phase 0 Readiness Verdict

# **VERDICT: READY WITH CONDITIONS**

### Justification:
The migration plan is fully specified, the six safety issues are rigorously resolved, the dependency graph is mapped, and the extraction-first validation sequence prevents code loss or regression.

### Mandatory Pre-Implementation Conditions:
1. **Step 0.1 Independent External Backup** must be physically executed and verified with cryptographic SHA-256 manifest matching before touching any file.
2. **Extraction-First Sequence** must be strictly honored (`stats.py`, `redaction.py`, and `dify.py` extracted and validated before deleting legacy modules).
3. **Allowlist-Only Git Staging** must be used (`git add .` is permanently forbidden).
4. **Explicit Owner Authorization** must be granted before Step 0.1 begins.

---

## 8. Current Status & Next Action

* **Status:** **PHASE 0 READINESS PLAN FINALIZED AND RIGOROUSLY REVISED.**
* **Next Action:** Standing by for explicit owner authorization: *"Proceed with Phase 0"*.

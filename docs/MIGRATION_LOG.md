# Migration Log: Generalizing MSU LLM Workbench into Runport

This document tracks the disposition of every module, package, and file in the repository as part of transitioning from the internal MSU LLM Workbench to the generic, open-source benchmarking platform: **Runport** (`runport`).

---

## 1. Source Package (`src/msu_llm_lab/` → `src/runport/`)

### 1.1 Root
| File | Action | Reason |
|---|---|---|
| `__init__.py` | **Generalize** | Rename to `runport/__init__.py`; expose package version and top-level public API. |
| `cli.py` (2,260 lines) | **Rewrite** | Split into modular `cli/` subcommands (`init`, `doctor`, `models`, `targets`, `datasets`, `plan`, `run`, `score`, `report`, `compare`, `budget`, `export`, `ui`, `tui`). |

---

### 1.2 Core (`core/`)
| File | Action | Reason |
|---|---|---|
| `core/__init__.py` | **Keep** | Standard package init. |
| `core/config.py` | **Rewrite** | Replace fixed CWD / relative `data/` and `PROJECT_ROOT` path math with workspace-rooted YAML configuration (`workbench.yaml`), `.env` support, and secure permissions (`ensure_secure_dotenv`). Change app name to `runport`. |
| `core/budget.py` | **Keep + Generalize** | Retain Decimal micro-dollar arithmetic, preflight bounds, and unresolved-spend blocking; make ceilings and policy configurable. |
| `core/budget_policy.py` | **Generalize** | Merge into configurable budget policy and audit trail; remove hardcoded $18/$2/$0.50/$0.02 defaults. |
| `core/live_guard.py` | **Generalize** | Abstract into pluggable `Approver` interface with `TypedPhraseApprover` (CLI/TUI), `UiApprover` (Web UI), and `TokenApprover` (CI `--approve <fingerprint>`). |

---

### 1.3 Storage (`storage/`)
| File | Action | Reason |
|---|---|---|
| `storage/__init__.py` | **Keep** | Standard package init. |
| `storage/db.py` | **Keep + Generalize** | Preserve SQLite WAL mode, budget ledger semantics, and unresolved-spend column; add additive migration for generic `results` table with nullable metrics, usage JSON, and steps JSON. Default database name becomes `runport.db`. |

---

### 1.4 Providers & Connectors (`providers/` → `connectors/`)
| File | Action | Reason |
|---|---|---|
| `providers/__init__.py` | **Keep** | Rename to `connectors/__init__.py`. |
| `providers/base.py` | **Keep + Generalize** | Generalize into `connectors/base.py`: `Target`, `TargetResult`, `capabilities`, `ProviderResponse`, secret scrubber (`scrub_secrets`). Extract provider-specific in-flight budget into a hook. |
| `providers/http.py` | **Keep + Generalize** | Move to `connectors/http.py`: retain `RetryingPoster` (bounded retry, 408/429/5xx, `Retry-After`, zero sleep after last attempt, no retry on malformed 200). |
| `providers/openrouter.py` | **Split & Generalize** | Split into `connectors/openai_compat.py` (generic OpenAI chat/completions) and `connectors/openrouter.py` (thin subclass for OpenRouter headers/routes). Remove hardcoded MSU HTTP headers (`X-Title: Runport`, repository URL) and hardcoded model blockers. |

---

### 1.5 Models & Catalog (`models/` → `catalog/`)
| File | Action | Reason |
|---|---|---|
| `models/__init__.py` | **Keep** | Rename to `catalog/__init__.py`. |
| `models/registry.py` | **Keep + Generalize** | Extract `Fact`, `FactStatus`, `RouteRecord`, `RouteOption` into `catalog/facts.py`. Delete hardcoded 10 participants, `CHECKED_ON = date(2026, 10, 15)`, and static `OR_*` constants. |
| `models/catalog.py` | **Delete** | Delete `DEFAULT_PORTFOLIO` (contained unverified placeholder entries including a 0-price bug); replace with pluggable catalog sources (live OpenRouter fetch, user YAML). |

---

### 1.6 Classification Stack (`classification/` → `workloads/classification/`, `scorers/`, `datasets/`, `runs/`)
| File | Action | Reason |
|---|---|---|
| `classification/__init__.py` | **Generalize** | Transition to generic workload package. |
| `classification/annotation.py` | **Generalize** | Move independent annotation, adjudication, named approval, and freezing into `datasets/annotation.py`. |
| `classification/benchmark.py` | **Generalize** | Move checkpointed executor, deterministic blocks, quarantine, and SHA-256 source hashing into `runs/executor.py`. |
| `classification/benchmark_detail.py` | **Delete** | One-off detail reporter for MSU study. |
| `classification/benchmark_report.py` | **Generalize** | Replace with generic Markdown/HTML report templates in `reports/`. |
| `classification/chat_adapter.py` | **Generalize** | Adapt chat payload construction to generic classification workload with configurable prompts. |
| `classification/claude_cost_validation_runner.py` | **Delete** | Study-specific script; contained forbidden raw network import violating package isolation. |
| `classification/contracts.py` | **Generalize** | Move generic case container, turn structures, and review statuses to `workloads/classification/contracts.py`; remove hardcoded `IntentLabel` (5 labels), `LeadCase`, and `Task.INTENT/LEAD`. |
| `classification/dataprep.py` | **Extract & Delete** | Extract generic text redaction and session-grouping logic into `datasets/redaction.py`; delete WhatsApp-specific CSV parsers and `user4` handling. |
| `classification/diagnostics.py` | **Generalize** | Move to `workloads/classification/diagnostics.py`. |
| `classification/jev_adapter.py` | **Move** | Move to `examples/plugins/jev_decisions_api/jev_adapter.py` as an optional plugin example. |
| `classification/jev_payloads.py` | **Move** | Move to `examples/plugins/jev_decisions_api/jev_payloads.py`. |
| `classification/lead_summary.py` | **Delete** | MSU admissions rule builder B1–B10; not generic. |
| `classification/master_intent_metrics.py` | **Delete** | Extract any unique metric calculation into `scorers/classification.py`, then delete. |
| `classification/metrics.py` | **Generalize** | Generalize into `scorers/classification.py` supporting arbitrary user-defined label sets. |
| `classification/privacy.py` | **Generalize** | Generalize fail-closed dispatch gates into `datasets/privacy.py` and `core/policy.py`. |
| `classification/realdata.py` | **Generalize** | Replace bespoke MSU real-data authorization flow with general `DataClassification` policy and Approver interface. |
| `classification/records.py` | **Generalize** | Generalize `AdapterResult` and `PredictionRecord` into `runs/records.py` supporting arbitrary workloads. |
| `classification/runner.py` | **Generalize** | Move to `runs/runner.py`, strictly preserving the 6-step guard order (authorization → privacy gate → readiness/budget preflight → send → validate → store). |
| `classification/serialization.py` | **Generalize** | Move generic prompt serialization to `workloads/classification/serialization.py`. |
| `classification/smoke.py` | **Generalize** | Move synthetic plan/execution testing into `workloads/smoke.py`. |
| `classification/splits.py` | **Keep + Move** | Move to `datasets/splits.py`: group-level leakage-safe splitting across TRAIN/DEV/TEST. |
| `classification/threshold.py` | **Keep + Move** | Move to `scorers/threshold.py`: DEV-only frozen threshold tuning applied unchanged to TEST. |
| `classification/validators.py` | **Generalize** | Generalize strict output validation patterns into `workloads/classification/validators.py`. |
| `classification/v2_*.py` (14 files) | **Delete** | Delete all 14 one-off v2 study files (`v2_benchmark_cli.py`, `v2_contracts.py`, `v2_evaluation_report.py`, `v2_final_comparison_generator.py`, `v2_final_comparison_pdf.py`, `v2_final_report_generator.py`, `v2_master_metrics.py`, `v2_pdf_report.py`, `v2_runner.py`, `v2_unrestricted_audited_generator.py`, `v2_unrestricted_cli.py`, `v2_unrestricted_metrics.py`, `v2_unrestricted_runner.py`, `v2_unrestricted_standalone_generator.py`, `v2_validators.py`). |

---

### 1.7 Observability (`observability/`)
| File | Action | Reason |
|---|---|---|
| `observability/__init__.py` | **Keep** | Standard package init. |
| `observability/aggregate.py` | **Keep + Generalize** | Retain honest aggregation (unknown values stay unknown, actual and estimated never conflated, nearest-rank percentiles). |
| `observability/analysis.py` | **Keep + Generalize** | Retain calibration from native distributions, agreement metrics, and quality analysis decoupled from MSU tasks. |
| `observability/events.py` | **Keep + Generalize** | Retain append-only `RequestEvent` schema, `EventStore`, and byte-offset `EventTail`. |
| `observability/export.py` | **Keep + Generalize** | Retain `trace-export-v1` format, redaction, atomic file writes, deterministic ZIP creation, and manifest generation. |
| `observability/labels.py` | **Keep + Generalize** | Retain approved label loader for supervised metrics. |
| `observability/monitor.py` | **Keep + Generalize** | Retain cooperative, read-only `LiveMonitor` subscription. |
| `observability/annotation_templates.py` | **Delete** | Study-specific HTML/markdown templates for admissions annotation. |
| `observability/budget_audit.py` | **Delete** | Study-specific budget audit generator. |
| `observability/bundle_verify.py` | **Delete** | Study-specific artifact verifier. |
| `observability/evaluation_document.py` | **Delete** | Hardcoded study narrative containing baked-in MSU counts. |
| `observability/evaluation_figures.py` | **Delete** | Hardcoded Matplotlib figures for the MSU study (also broke under Matplotlib 3.9+). |
| `observability/evaluation_redesign.py` | **Delete** | One-off PDF layout generator for admissions evaluation. |
| `observability/evaluation_report.py` | **Extract & Delete** | Extract `wilson`, `boot_ci`, and `holm` into `scorers/stats.py` (B10); delete the narrative report generator. |
| `observability/evaluation_runner.py` | **Delete** | Study-specific evaluation bundle orchestrator. |

---

### 1.8 Terminal UI (`tui/`)
| File | Action | Reason |
|---|---|---|
| `tui/__init__.py` | **Keep** | Standard package init. |
| `tui/app.py` | **Keep + Generalize** | Preserve Rich full-screen terminal mechanics; update branding to Runport; support dynamic view tabs. |
| `tui/banner.py` | **Keep + Generalize** | Re-brand to Runport terminal identity. |
| `tui/health.py` | **Keep + Generalize** | Retain system diagnostics; remove hardcoded MSU KB markdown file checks. |
| `tui/input.py` | **Keep** | Retain terminal keyboard event parsing. |
| `tui/live_views.py` | **Keep + Generalize** | Retain view-model rendering, Trace Explorer, and execution header; decouple from hardcoded MSU tasks. |
| `tui/screens.py` | **Keep + Generalize** | Replace static 16-entry `NAV_KEYS`/`NAV_ITEMS` with dynamically registered views. |
| `tui/telemetry.py` | **Keep** | Retain psutil system sampling and request view-model buffering. |
| `tui/theme.py` | **Keep** | Retain slate/navy background and muted purple selection styling. |
| `tui/welcome.py` | **Keep + Generalize** | Retain launcher menu loop; update welcome message to Runport. |

---

### 1.9 Workflow Integration (`dify_eval/` → `connectors/dify.py`)
| File | Action | Reason |
|---|---|---|
| `dify_eval/client.py` | **Generalize** | Repurpose `post_chat_message` into core `connectors/dify.py` supporting blocking chat and workflow run endpoints. |
| `dify_eval/rag_stream.py` | **Generalize** | Repurpose SSE chunk streaming into `connectors/dify.py`. |
| `dify_eval/cases.py`, `cli.py`, `extras.py`, `plan.py`, `report.py`, `runner.py`, `rag_*.py`, etc. (18 files) | **Delete** | Delete study-specific Dify evaluation scripts, reports, and runners once generic connector is in place. |

---

### 1.10 Other Packages to Delete or Move
| Package / File | Action | Reason |
|---|---|---|
| `labeled_eval/` (13 files) | **Extract & Delete** | Extract `stats.py` (`boot_ci`, `holm`, `wilson`) into `scorers/stats.py`; delete remaining one-off 120/200-case study files. |
| `lead_report_final/` (4 files) | **Delete** | One-off study report generator. |
| `v2_report_final/` (6 files) | **Delete** | One-off study report generator. |
| `audit/` (4 files) | **Move** | Move markdown admissions KB validator to `examples/plugins/kb_audit/`. |
| `remediation/` (3 files) | **Move** | Move admissions KB clean-copy engine to `examples/plugins/kb_audit/`. |
| `rag/` (4 files) | **Keep + Generalize** | Move BM25 retriever to `workloads/rag/`; make retriever a pluggable Target; remove `CONTRADICTORY_RECORD_IDS` (B9). |
| `traces/` (4 files) | **Keep as Optional** | Move Langfuse trace importer and failure classifier to `importers/langfuse/`; strip MSU terminology. |
| `retro_split/` (3 files) | **Delete** | Fixed 220-case retrospective split for MSU. |
| `dataset/` (2 files) | **Keep + Generalize** | Move `leakage.py` and `manager.py` to `datasets/`. |
| `schemas/` (3 files) | **Keep + Generalize** | Generalize evaluation cases and score schemas. |
| `evaluation/` (2 files) | **Generalize** | Move `runner.py` to `workloads/generation.py`; delete `RubricEvaluator` or rename to `lexical_overlap` in `scorers/`. |

---

## 2. Test Suite (`tests/`)

| Test File | Action | Reason |
|---|---|---|
| `tests/classification/test_splits_metrics_privacy.py` | **Port & Generalize** | Retain data privacy gate and leakage tests; update import checks. |
| `tests/classification/test_contracts.py` | **Port & Generalize** | Adapt to generic case contract. |
| `tests/classification/test_validators.py` | **Port & Generalize** | Adapt to generic strict validators. |
| `tests/classification/test_threshold.py` | **Port** | Invariant: DEV-only threshold selection frozen for TEST. |
| `tests/classification/test_runner_adapters.py` | **Port & Generalize** | Invariant: fake transport adapter invocation. |
| `tests/classification/test_runner_telemetry.py` | **Port & Generalize** | Invariant: lifecycle telemetry emitted around each request. |
| `tests/test_budget.py` | **Port & Generalize** | Invariant: spend ceilings, preflight estimation, micro-dollar arithmetic. |
| `tests/test_budget_policy.py` | **Port & Generalize** | Invariant: budget overrides and audit history. |
| `tests/test_ledger_simulated.py` | **Port** | Invariant: simulated transactions separated from actuals. |
| `tests/test_unresolved_spend.py` | **Port** | Invariant: unresolved spend blocks future live requests. |
| `tests/test_live_safety.py` | **Port & Generalize** | Invariant: fail-closed gates, live authorization required. |
| `tests/test_providers.py` | **Port & Generalize** | Invariant: RetryingPoster retry rules, 429 backoff, secret scrubbing. |
| `tests/test_observability_events.py` | **Port** | Invariant: append-only JSONL, EventTail offset recovery. |
| `tests/test_observability_analysis.py` | **Port** | Invariant: calibration, agreement, quality metrics. |
| `tests/test_trace_export.py` | **Port** | Invariant: trace-export-v1 redaction, deterministic zip output. |
| `tests/test_dataset.py` | **Port** | Invariant: dataset management, n-gram leakage prevention. |
| `tests/test_tui.py` | **Port & Generalize** | Retain TUI keyboard navigation, pane switching; de-brand. |
| `tests/test_launcher_pty.py` | **Port & Generalize** | Retain interactive terminal launcher tests. |
| `tests/test_model_registry.py` | **Port & Generalize** | Adapt to dynamic catalog facts. |
| `tests/test_dify_eval.py`, `tests/test_dify_rag_eval.py` | **Generalize** | Adapt into connector contract suite for Dify. |
| `tests/test_candidate_v3_prompt_rules.py`, `tests/test_haiku_compat.py`, `tests/test_jev_*.py`, `tests/test_lead_report_final.py`, `tests/test_main_intent_*.py`, `tests/test_v2_*.py`, `tests/test_labeled_eval.py`, `tests/test_evaluation_report.py`, `tests/test_audit.py`, `tests/test_remediation.py` | **Delete or Move** | Delete tests tied directly to deleted MSU study modules; move KB audit tests to `examples/plugins/kb_audit/`. |

---

## 3. Documentation, Data & Root Artifacts

| Path | Action | Reason |
|---|---|---|
| `AGENTS.md` | **Rewrite** | Rewrite to reflect Runport platform architecture, safety model, and clean boundaries. |
| `README.md` | **Rewrite** | Rewrite to present the generic Runport platform, quickstart, and features. |
| `docs/ARCHITECTURE.md`, `CURRENT_ARCHITECTURE.md` | **Rewrite** | Update to reflect Runport's Target / Workload / Scorer / Run architecture. |
| `docs/PROJECT_MAP.md` | **Update** | Update file and test counts across phases. |
| `docs/DATASET_CLEANING.md`, `LABELED_EVALUATION.md`, `PROMPT_DECISIONS.md`, `RAG_EVAL_MODEL_PRICES.md`, `REAL_BENCHMARK.md` | **Archive/Delete** | Study-specific documentation to be replaced by generic documentation (`concepts.md`, `quickstart.md`, `connectors.md`, `scorers.md`). |
| Root CSVs, markdown prompts, and KB copies (`september_to_october.csv`, `Copy of MSU *.md`, etc.) | **Remove from repo** | Confidential admissions and student data; must not exist in open-source repository. |
| `assets/` | **Replace** | Replace MSU-branded screenshots and logo with generic Runport assets. |

---

## 4. Legacy Identity De-Branding & Renaming Inventory (Runport Transition)

This section maps all occurrences of the legacy identity ("MSU", "msu_llm_lab", "MSU LLM Workbench") across the repository, distinguishing **public-facing branding** from **internal research history**.

### 4.1 Boundary Definition: Public Branding vs. Research History
* **Public-Facing Branding & Code Identifiers (MUST BE RENAMED TO RUNPORT):**
  * Package directories, import paths, CLI command names, pyproject metadata.
  * Outbound HTTP headers (sent to external model providers).
  * Terminal UI banners, window titles, and console status messages.
  * Storage file defaults (`workbench.db` → `runport.db`).
  * Environment variable prefixes (`MSU_LLM_SKIP_DOTENV` → `RUNPORT_SKIP_DOTENV`).
  * Public documentation (`README.md`, `docs/ARCHITECTURE.md`).
* **Internal Research History & Migration Provenance (PRESERVED IN HISTORICAL CONTEXT):**
  * Historical migration notes in this document detailing where legacy packages originated.
  * Audit records explaining why the internal admissions KB had structural defects.
  * Research notes explaining why the initial study investigated specific Malaysian Ringgit (RM) tuition fees.
  * *Rule:* Never perform blind find-and-replace of "MSU" in historical changelogs, research logs, or provenance explanations.

---

### 4.2 Comprehensive Inventory of Files Requiring Renaming or Metadata Changes

#### A. Core Package & Configuration Files
| File | Current Value / Pattern | Required Runport Identifier |
|---|---|---|
| `pyproject.toml:6` | `name = "msu-llm-lab"` | `name = "runport"` |
| `pyproject.toml:8` | `description = "...MSU admissions..."` | `description = "Open-source LLM, prompt, and workflow benchmarking platform"` |
| `pyproject.toml:12` | `authors = [{ name = "MSU Research Team" }]` | `authors = [{ name = "Runport Contributors" }]` |
| `pyproject.toml:40` | `msu-llm-lab = "msu_llm_lab.cli:app"` | `runport = "runport.cli:app"` |
| `pyproject.toml:48` | `packages = ["src/msu_llm_lab"]` | `packages = ["src/runport"]` |
| `src/msu_llm_lab/` (directory) | `src/msu_llm_lab/` | `src/runport/` |
| `src/msu_llm_lab/core/config.py:42` | `app_name: str = "msu-llm-lab"` | `app_name: str = "runport"` |
| `src/msu_llm_lab/core/config.py:45` | `db_filename: str = "workbench.db"` | `db_filename: str = "runport.db"` |
| `src/msu_llm_lab/core/config.py:89` | `os.environ.get("MSU_LLM_SKIP_DOTENV")` | `os.environ.get("RUNPORT_SKIP_DOTENV")` |

#### B. Outbound Network & Provider Attribution Headers
| File | Current Value / Pattern | Required Runport Identifier |
|---|---|---|
| `src/msu_llm_lab/providers/openrouter.py:218` | `HTTP-Referer: https://github.com/Sudharsanselvaraj/Model-Systems-Workbench` | `HTTP-Referer: https://github.com/Sudharsanselvaraj/runport` |
| `src/msu_llm_lab/providers/openrouter.py:219` | `X-Title: MSU LLM Workbench` | `X-Title: Runport` |

#### C. User Interfaces & CLI
| File | Current Value / Pattern | Required Runport Identifier |
|---|---|---|
| `src/msu_llm_lab/cli.py:114` | `Exiting MSU LLM Workbench. Goodbye.` | `Exiting Runport. Goodbye.` |
| `src/msu_llm_lab/cli.py:2170` | `MSU LLM Workbench — Budget Status` | `Runport — Budget Status` |
| `src/msu_llm_lab/tui/app.py:1` | Docstring: `...MSU LLM Workbench` | Docstring: `...Runport` |
| `src/msu_llm_lab/tui/app.py:501` | `Exited MSU LLM Workbench.` | `Exited Runport.` |
| `src/msu_llm_lab/tui/welcome.py:135` | `Welcome to MSU LLM Workbench` | `Welcome to Runport` |
| `src/msu_llm_lab/tui/health.py:38-42` | Checks for `MSU General KB` and `MSU Programmes KB` | Generic workspace health checks (e.g. SQLite, Python runtime, workspace config) |
| `src/msu_llm_lab/traces/reporter.py:44` | `# MSU LLM Workbench — Trace Diagnostic Report` | `# Runport — Trace Diagnostic Report` |

#### D. Python Imports Across Codebase
* **Scope:** 1,017 occurrences across `src/` and `tests/` of `from msu_llm_lab...` and `import msu_llm_lab...`.
* **Required Change:** In Phase 0/1, systematically re-target all imports to `runport.*`.

#### E. Public Documentation & Brand Assets
| File / Asset | Current State | Required Runport State |
|---|---|---|
| `README.md` | MSU LLM Workbench branding and header logo | Runport header, clean open-source feature set, CLI commands `runport ...` |
| `AGENTS.md` | Encodes admissions-specific rules (rules 3, 10, 11) | Generic development guidelines and budget/safety invariants for Runport |
| `assets/Lavender Branching Tech Panels.png` | MSU logo | Replace with Runport project visual asset |
| `assets/readme/*.png` | Screenshots showing "MSU LLM Workbench" | Regenerate with synthetic Runport UI runs |

---

## 5. Phase 0 Implementation Summary & Verification (2026-11-02)

### 5.1 Verification Checklist
- [x] **Master Backup**: Verified complete, independent master backup at `/Users/sudharsan/Downloads/MSU_Workbench_Master_Backup_20261102` (10,528 files, SHA-256 manifest generated).
- [x] **Confidentiality Clearance**: Purged root conversation exports (`september_to_october.csv`), authoritative prompt files (`main_intent_classifier.md`, `lead_qualification_prompt.md`), internal KB copies, evaluation/report scripts, obsolete experiment directories (`experiments/`, `scratch/`), and private test datasets.
- [x] **Zero Secret Leakage**: Verified zero provider API keys, phone numbers, or student emails across all tracked files.
- [x] **Extraction of Generic Components**:
  - `src/runport/scorers/stats.py`: Wilson CIs, bootstrap CI, Cohen's Kappa, Holm correction, PRF metrics.
  - `src/runport/datasets/redaction.py`: Regex PII redaction and salted hash pseudonyms.
  - `src/runport/connectors/dify.py`: Dify chat and SSE streaming integration with secret scrubbing.
  - `src/runport/catalog/models.py`: Model candidate data contract.
- [x] **Decoupled Plugin Relocation**:
  - `examples/plugins/kb_audit/`: Deterministic KB audit and remediation engine with isolated tests.
  - `examples/plugins/jev_decisions_api/`: Jev Decisions API payload builder and adapter with isolated tests.
- [x] **Package Structure & De-Branding**:
  - Package renamed from `msu_llm_lab` to `runport`.
  - CLI script updated to `runport = "runport.cli:app"`.
  - TUI, health checks, error handlers, and HTTP headers systematically de-branded to Runport.
- [x] **Targeted Git Protection**:
  - Replaced broad exclusions with precise rules in `.gitignore`.
  - Cleaned local runtime databases and temporary run artifacts.
- [x] **Complete Test Suite Baseline**:
  - Main test suite: **658 passing** (including 5 PTY launcher tests), 5 skipped (due to intentionally purged confidential prompts).
  - Plugins test suite: **26 passing**, 5 skipped.
  - Total tests passing: **684 passing**, 0 failing, 0 errors.
  - External CLI execution verified cleanly from `/tmp`.

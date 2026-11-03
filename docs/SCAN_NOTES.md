# Scan Notes: Security & Privacy Leak Audit

This document records and justifies all matches identified during the Phase A repository leak scan (`msu|admission|whatsapp|user4|september_to_october|REC-1886`).

Every match listed below has been verified as either a privacy enforcement sentinel, a migration decision record, an explicit exclusion rule in `.gitignore`, or a synthetic test fixture. No proprietary or confidential production data is present.

---

## 1. Exclusions & Git Configuration (`.gitignore`)

| File | Line(s) | Match | Classification & Justification |
|---|---|---|---|
| `.gitignore` | 68, 72, 76, 77 | `september_to_october.csv`, `msu_intent*.csv`, `msu_rag_test_suite*.csv`, `Copy of MSU *.md` | **Exclusion Rule.** Explicit ignore patterns ensuring legacy or local files can never be staged or committed to the repository. |

---

## 2. Migration & Architecture Documentation (`docs/`)

| File | Line(s) | Match | Classification & Justification |
|---|---|---|---|
| `docs/DATASET_CLEANING.md` | 5, 18, 25 | `september_to_october.csv`, `user4` | **Privacy Documentation.** Documents historical verification that raw phone numbers (`user4`) were stripped and never ingested into benchmarks or exported artifacts. |
| `docs/IMPLEMENTATION_PLAN.md` | 31 | `admissions queries` | **Migration Scope.** Historical implementation record describing the decoupling of domain-specific terminology. |
| `docs/LIVE_DASHBOARD.md` | 52 | `user4` | **Privacy Specification.** Specifies privacy safeguards in the terminal dashboard ensuring `user4` is discarded and identifiers redacted. |
| `docs/MIGRATION_LOG.md` | 7 | `admissions queries` | **Migration Record.** Documents the permanent removal and exclusion of historical conversational data. |
| `docs/OPEN_DECISIONS.md` | 16-255 | `MSU`, `admissions`, `september_to_october`, `user4` | **Architecture Decision Records (ADRs).** Documents formal decisions regarding project rebranding (Runport), Apache 2.0 licensing, confidential data exclusion procedures, and clean-slate repository policies. |
| `docs/REAL_BENCHMARK.md` | 13-174 | `admissions`, `user4` | **Security Specifications.** Formal contract documentation specifying typed human approval and privacy constraints before any live execution. |

---

## 3. Legacy Classification Subsystem (`src/runport/classification/` & `tests/classification/`)

*Note: The classification subsystem is scheduled for generalized refactoring or deprecation in Phase B.*

| File | Match Context | Classification & Justification |
|---|---|---|
| `src/runport/classification/dataprep.py` | `user4`, `september_to_october` | **Privacy Enforcement.** Verifies that legacy phone prefix `user4` is dropped at ingestion and asserts absence of unredacted files. |
| `src/runport/classification/splits.py` | `user4` | **Privacy Enforcement.** Implements `assert_no_user4` validation function to reject any split containing legacy identifiers. |
| `src/runport/classification/benchmark_report.py` | `admissions` | **Evaluation Labels.** Legacy task and domain label types. |
| `src/runport/classification/lead_summary.py` | `admissions` | **Evaluation Labels.** Lead qualification domain types. |
| `src/runport/classification/realdata.py` | `real_admissions_derived` | **Safety Guard.** Spending and data-governance flags ensuring unapproved real data is blocked from external networks. |
| `src/runport/classification/runner.py` | `admissions` | **Evaluation Category.** Benchmark scenario tag. |
| `src/runport/classification/smoke.py` | `september_to_october` | **Integrity Assertion.** Asserts that raw legacy CSVs do not exist in test imports. |
| `tests/classification/test_contracts.py` | `user4` | **Privacy Sentinel Test.** Asserts that Pydantic contract fails if `user4` is provided. |
| `tests/classification/test_dataprep.py` | `USER4_SENTINEL`, `user4` | **Privacy Sentinel Test.** Verifies that `user4` values are never written to any output file or manifest. |
| `tests/classification/test_lead_summary.py` | `admissions office` | **Synthetic Test Message.** Synthetic dialog turn in test case. |
| `tests/classification/test_real_benchmark.py` | `real_admissions_derived` | **Safety Guard Test.** Verifies that spend guards block runs without typed operator approval. |
| `tests/classification/test_smoke.py` | `september_to_october` | **Integrity Test.** Asserts that raw data imports are strictly absent. |
| `tests/classification/test_splits_metrics_privacy.py` | `user4`, `september_to_october` | **Privacy Sentinel Test.** Asserts that `assert_no_user4` raises on illegal fields and validates dataset cleanliness. |

---

## 4. Observability, Traces, & TUI (`src/runport/`)

| File | Line(s) | Match Context | Classification & Justification |
|---|---|---|---|
| `src/runport/observability/export.py` | 134, 150, 154 | `user4` | **Privacy Scrubbing.** Explicit redaction logic in trace exporter that removes `user4` and sensitive metadata before writing trace records. |
| `src/runport/traces/analyzer.py` | 154, 232 | `admissions flow`, `admissions calendar` | **Diagnostic Taxonomy.** Diagnostic rule templates for routing misclassification and KB freshness analysis. |
| `src/runport/tui/screens.py` | 1259 | `user4 excluded` | **TUI Information Banner.** Status line explaining privacy invariants to the terminal operator. |

---

## 5. Example Plugins (`examples/plugins/`)

| File | Line(s) | Match Context | Classification & Justification |
|---|---|---|---|
| `examples/plugins/kb_audit/remediation/registry.py` | 128 | `Admissions Calendar` | **Synthetic Metadata.** Example action description in plugin demo. |
| `examples/plugins/kb_audit/tests/test_audit.py` | 35 | `admissions portal` | **Synthetic Test Fixture.** Synthetic query string in test fixture. |

---

## 6. Offline Test Suite (`tests/`)

| File | Match Context | Classification & Justification |
|---|---|---|
| `tests/test_dataset.py` | `admission requirements` | **Synthetic Benchmark Query.** Synthetic queries for "Novatech Institute" evaluation cases. |
| `tests/test_rag_benchmark.py` | `Consult admissions` | **Synthetic Expected Answer.** Synthetic ground truth answer string for out-of-scope RAG cases. |
| `tests/test_trace_export.py` | `user4` | **Privacy Sentinel Test.** Verifies that `user4` and API keys are completely purged from exported archives. |
| `tests/test_traces.py` | `admission`, `undergraduate_admissions` | **Synthetic Trace Fixture.** Synthetic span names and mock query strings for trace ingestion tests. |


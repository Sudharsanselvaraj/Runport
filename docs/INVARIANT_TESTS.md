# Architectural Invariant Verification Map

This document establishes the verified cryptographic and behavioral proof mapping each of the 16 Runport architectural invariants to its exact test identifier in the offline automated test suite.

All tests operate completely offline with blocked sockets and mock/replay transports.

---

| # | Invariant | Description / Guarantee | Test Identifier (`file::name`) | Status |
|---|---|---|---|---|
| 1 | **Null is not 0** | Missing tokens, latency, confidence, or cost remain `None` / `UNAVAILABLE`. Telemetry is never fabricated or defaulted to zero. | `tests/test_workloads_and_scorers.py::test_scorers_null_is_not_zero`<br>`tests/test_trace_export.py::test_every_trace_field_is_present_and_nulls_are_preserved`<br>`tests/test_core_invariants.py::test_db_columns_accuracy_and_tokens_nullable`<br>`tests/test_core_invariants.py::test_unknown_price_model_runs_with_unavailable_estimate_and_requires_per_case_cap` | Verified |
| 2 | **Fixed Provenance Vocabulary** | Spend is strictly partitioned into `ACTUAL`, `ESTIMATED`, `UNRESOLVED`, and `UNAVAILABLE` (`$0.00`). Replays book `REPLAYED`. | `tests/test_unresolved_spend.py::test_actual_estimated_simulated_and_unresolved_spend_stay_distinct` | Verified |
| 3 | **Unresolved Spend Blocks Execution** | Unresolved ledger entries block subsequent live preflight fail-closed until reconciled. | `tests/test_unresolved_spend.py::test_unresolved_entry_has_no_invented_amount_and_blocks_preflight` | Verified |
| 4 | **Strict Runner Guard Order** | Execution strictly follows: Authorization Check → Privacy Gate → Preflight Budget → Transport → Validation → Spend Booking. | `tests/test_classification.py::test_runner_strict_guard_order` | Verified |
| 5 | **Cryptographic Plan Fingerprint** | SHA-256 fingerprint binds candidate models, endpoint routes, dataset hash, prompt template hash, and budget caps. Single-use token approver cannot be reused. | `tests/test_runs_engine.py::test_plan_fingerprint_deterministic_and_binds_inputs`<br>`tests/test_core_invariants.py::test_token_approver_mismatched_and_consumed_cannot_be_reused` | Verified |
| 6 | **Non-Interactive Live Run Refused** | Live inference requires explicit typed operator approval or a valid plan-bound token approver; headless runs without approval fail closed. | `tests/test_live_safety.py::test_refusal_when_flag_present_but_phrase_missing`<br>`tests/test_budget_policy.py::test_cli_refuses_without_an_interactive_terminal` | Verified |
| 7 | **Pinned Provider Routes with No Silent Fallback** | Requests route strictly through user-pinned provider routes; provider failover without explicit config is refused. | `tests/test_live_safety.py::test_model_catalog_pinned_provider_routing` | Verified |
| 8 | **Bounded Retry with Backoff** | Only retryable statuses (429, 5xx) with bounded exponential backoff and `Retry-After` honoring; malformed 200 is not retried. | `tests/test_providers.py::test_http_transport_retry_429_honors_retry_after` | Verified |
| 9 | **Zero Leakage & Secret Scrubbing** | API keys, bearer tokens, passwords, and secrets are scrubbed before reaching events, logs, or exports. | `tests/test_providers.py::test_secret_scrubber_masks_sensitive_patterns` | Verified |
| 10 | **Group-Level Splits with Zero Leakage** | Group-level partitioning prevents data leakage across train, dev, and test sets. Leakage detector asserts disjoint sets. | `tests/test_classification.py::test_splits_group_assignment_and_privacy`<br>`tests/test_dataset.py::test_leakage_detector_exact_and_normalized_overlap` | Verified |
| 11 | **DEV-Only Threshold Selection Frozen Before TEST** | Decision thresholds and hyperparameters calibrate on DEV only, freeze, and evaluate unchanged on TEST. | `tests/test_classification.py::test_dev_calibration_and_held_out_frozen_evaluation`<br>`tests/test_observability_analysis.py::test_binary_threshold_is_selected_on_dev_only_and_frozen_before_test` | Verified |
| 12 | **Strict Output Validation** | Model outputs undergo strict schema and value validation before scoring or acceptance into dataset. | `tests/test_classification.py::test_validate_classification_output` | Verified |
| 13 | **Whole-Batch Privacy Gate** | Privacy check inspects the entire batch before any network transport or inference call is initiated. | `tests/test_classification.py::test_whole_batch_privacy_gate_rejects_before_any_request` | Verified |
| 14 | **Immutable Sources** | Source datasets are SHA-256 hashed before and after evaluation to guarantee immutability. | `tests/test_dataset.py::test_immutable_source_hashing_verifies_before_and_after` | Verified |
| 15 | **Agreement is Not Correctness** | Model-to-model consensus is never presented as accuracy or ground truth. Unanimous errors are highlighted. | `tests/test_observability_analysis.py::test_agreement_is_not_correctness`<br>`tests/test_dashboard_live.py::test_agreement_view_labels_agreement_as_not_correctness` | Verified |
| 16 | **Supervised Metrics Require Human Ground Truth** | Supervised metrics (accuracy, F1, calibration) are computed exclusively from human-approved annotations. | `tests/test_observability_analysis.py::test_quality_metrics_come_only_from_approved_labels`<br>`tests/test_dashboard_live.py::test_quality_view_needs_approved_labels_and_never_substitutes_predictions` | Verified |


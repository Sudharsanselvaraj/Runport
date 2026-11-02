# Current Architecture: Runport (`runport`)

**Status**: Operational Benchmarking Architecture  
**License**: Apache 2.0  

Runport enforces real-requests-only execution, hard spend boundaries, human-approved ground-truth integrity, and local-first data privacy.

---

## Key Invariants

1. **Zero Simulation**: Production pipelines never fake or fabricate responses, token counts, latency, or costs.
2. **Fail-Closed Spend Caps**: Hard budget limits ($18 total, $2 pilot, $0.50 run, $0.02 case) enforced preflight and in-flight.
3. **Ground Truth Independence**: Supervised metrics require human-approved labels; model consensus is never treated as accuracy.
4. **Interactive Approval**: Outbound live requests require interactive human confirmation bound to the execution plan fingerprint.
5. **Sanitized Storage**: Evaluation records, traces, and SQLite WAL ledgers remain local and redacted.

See [ARCHITECTURE.md](ARCHITECTURE.md) for full subsystem details and component data flow diagrams.

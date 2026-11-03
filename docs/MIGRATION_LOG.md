# Migration Note: Evolution of Runport

Runport originated from an internal domain-specific evaluation tool and was generalized into a standalone, local-first, open-source LLM, prompt, and workflow benchmarking platform.

### What Was Removed & Decoupled
1. **Confidential & Domain-Specific Data**:
   - All internal conversational exports, candidate logs, and domain-specific admissions queries were permanently excluded from tracking.
   - Evaluative benchmarks were replaced with synthetic, reproducible benchmarks (`synthetic_seed_eval.jsonl` and synthetic RAG benchmarks).

2. **Specialized Protocols & Custom Integrations**:
   - Decoupled one-off enterprise workflows (such as specialized HTTP decision APIs and knowledge-base audit tooling) into standalone reference plugins under `examples/plugins/`.

3. **Core Generalization**:
   - Universal `Target` abstraction supporting raw models, prompt wrappers, and multi-step workflows (Dify, Flowise, Langflow, n8n, LangGraph).
   - Strict provenance categorization: `ACTUAL` (provider reported), `ESTIMATED` (catalog rate × reported tokens), `UNRESOLVED` (cost unknown), and `UNAVAILABLE` (zero-cost / local).
   - Tamper-evident, cryptographic plan fingerprinting binding target rosters, datasets, and spend limits to execution authorization.

### Preserved Architectural Invariants
- Fail-closed spend governance with hard budget ceilings.
- Immutable source inputs with pre- and post-execution SHA-256 validation.
- Supervised metrics strictly derived from human-approved ground truth.
- Zero external tracking, zero diagnostic pings, and automatic secret scrubbing.

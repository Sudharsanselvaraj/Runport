# Contributing to Runport

Thank you for your interest in contributing to Runport! We welcome contributions, bug fixes, and suggestions to advance honest, cost-controlled LLM benchmarking.

---

## 1. Development Environment

Runport uses [`uv`](https://docs.astral.sh/uv/) for high-speed, reproducible Python dependency management.

```bash
# Clone the repository
git clone https://github.com/Sudharsanselvaraj/Runport.git
cd Runport

# Install all development and reporting dependencies
uv sync --extra dev --extra report
```

---

## 2. Testing Guidelines

All automated tests in Runport run **completely offline**. Test executions use fake transports, mock handlers, and blocked network sockets.

```bash
# Run core test suite (offline)
uv run pytest

# Run plugin test suite
uv run pytest examples/plugins

# Run specific module tests
uv run pytest tests/test_connectors.py
uv run pytest tests/test_budget.py
```

Before submitting a pull request, verify:
1. All tests pass cleanly (`350+` tests).
2. No new tests require internet access, live API credentials, or spend.
3. Code changes preserve or expand test coverage.

---

## 3. Core Architectural Invariants

Contributions must respect Runport's architectural invariants:

1. **Null is not 0**: Missing tokens, latency, confidence, or cost remain `None` / `UNAVAILABLE`. Never fabricate or default missing telemetry to zero.
2. **Fixed Provenance Vocabulary**: Spend is strictly categorized as `ACTUAL`, `ESTIMATED`, `UNRESOLVED`, or `UNAVAILABLE`.
3. **Runner Guard Order**:
   `Authorization Check` → `Privacy Gate` → `Preflight Budget & Context Check` → `Transport Execution` → `Strict Validation` → `Persistence` → `Spend Booking`.
4. **Fail-Closed Spend Caps**: Unresolved ledger entries block subsequent runs until reconciled.
5. **Cryptographic Fingerprinting**: Plans bind candidate models, routes, dataset hashes, prompt templates, and budget limits via SHA-256.
6. **Immutable Sources**: Source datasets are verified with SHA-256 before and after runs.
7. **Zero Simulation in Core**: Providers and mock responses belong strictly in `tests/`, never in `src/`. Replay executions carry provenance `REPLAYED` and book `$0.00`.
8. **Agreement is Not Correctness**: Model consensus is never presented as accuracy. Supervised metrics require human ground truth.

---

## 4. Git & Commit Hygiene

- **Commit Granularity**: Make small, focused commits with imperative commit messages (e.g., `feat(cli): add plan dry-run flag`, `fix(budget): reject negative spend amounts`).
- **No Secrets**: Never commit `.env` files, API keys, SQLite databases (`*.db`, `*.db-wal`), or real evaluation logs. Run `gitleaks detect` locally before pushing.
- **Clean Diffs**: Ensure code formatting and linting pass without unneeded whitespace or unrelated refactoring.

---

## 5. Submitting Pull Requests

1. Fork the repository and create a descriptive feature branch (`git checkout -b feature/my-feature`).
2. Implement your changes with corresponding tests.
3. Run the full test suite and gitleaks scan.
4. Open a Pull Request against `main`. Provide a clear summary of the changes and confirm all invariant checks pass.

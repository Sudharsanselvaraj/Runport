---
title: Running tests
description: Run the offline test suites for the core package and the reference plugins.
---

Every test runs offline. Network sockets are blocked and transports are replaced with fakes, so no test needs a key or spends money.

```bash
uv run pytest                     # core suite
uv run pytest examples/plugins    # reference plugins
```

Run one module:

```bash
uv run pytest tests/test_connectors.py
uv run pytest tests/test_budget.py
uv run pytest tests/test_web_api.py
```

## What the CI runs

On every push and pull request:

1. `ruff check` and `ruff format --check`
2. `mypy`
3. `pytest -v` for the core suite and for `examples/plugins`, with the `dev` and `report` extras
4. A frontend build with Node 20

## Writing tests

- Put test doubles under `tests/` only; core modules must not simulate providers.
- Do not open sockets or require credentials.
- When you touch an invariant (cost provenance, guard order, null handling), add a test that would fail if it were weakened. `docs/INVARIANT_TESTS.md` in the repository maps each invariant to its tests.

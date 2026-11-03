## Description
Briefly describe the purpose of this change and link relevant issues.

## Checklist
- [ ] Conforms to repository invariants in `AGENTS.md` and `docs/DECISIONS.md`.
- [ ] No fabricated telemetry (missing values remain `None` / `UNAVAILABLE`).
- [ ] Spend limits and preflight plan approvals preserved.
- [ ] Secrets and API keys are automatically scrubbed from request logs and exports.
- [ ] Offline tests added under `tests/` with simulated transports.
- [ ] All tests pass: `uv run pytest` and `uv run pytest examples/plugins`.
- [ ] Linting and type checking pass: `uv run ruff check` and `uv run mypy`.
- [ ] No personal paths, usernames, or live credentials committed.

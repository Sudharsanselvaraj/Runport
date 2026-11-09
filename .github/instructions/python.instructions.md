---
applyTo: "**/*.py"
---
# Python Code Review & Development Instructions

Apply these rules when authoring or reviewing Python code across Runport:

1. **Pydantic v2 Patterns**:
   - Use `model_dump()`, `model_validate()`, and `Field(...)`.
   - Never use deprecated Pydantic v1 methods (`.dict()`, `.parse_obj()`).
   - Use `model_validator(mode="before"|"after")` and `field_validator`.

2. **Null is Not Zero**:
   - Missing tokens, latency, confidence, or cost MUST remain `None` or `UNAVAILABLE`.
   - Never default or coerce missing numeric telemetry to `0` or `0.0`.

3. **Database Concurrency & Idempotency**:
   - All SQLite migrations must be idempotent. Use `_add_column_if_missing` or check table schema info before running `ALTER TABLE`.
   - Ensure database operations execute within proper WAL transaction boundaries.

4. **Tenant Scoping**:
   - All queries accessing runs, plans, targets, traces, or ledger entries must include `WHERE project_id = ?` (or pass `project_id` to database helper methods).

5. **Testing & Test Doubles**:
   - Core modules (`src/runport/**`) must never contain simulation, mock branching, or fake transport logic.
   - All test doubles and mocks belong strictly under `tests/`.
   - Tests run strictly offline; sockets are blocked.

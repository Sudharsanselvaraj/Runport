# Offline HTTP Workflow Example

Demonstrates configuring and executing Runport's `HttpWorkflowConnector` against a custom REST endpoint with template substitution and JSON dot-path output extraction.

---

## Files
- `run.py`: Spawns an in-process HTTP mock server, applies payload templating, calls the service, and parses `data.summary`.

---

## How to Run

```bash
uv run python examples/http-workflow/run.py
```

Runs completely offline in `<0.2s`.

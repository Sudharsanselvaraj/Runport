"""A local, deterministic benchmark target used by the MCP server integration tests (no network)."""


def answer(case):
    return case.get("expected_answer") or "no answer"

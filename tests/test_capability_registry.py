"""The connector capability registry is the single source of truth, and every claim in it is backed by code."""

import re
from pathlib import Path

import pytest

from runport.connectors import registry
from runport.connectors.registry import CONNECTOR_MATRIX, CONNECTORS, MATRIX_BEGIN, MATRIX_END, YES, render_matrix_markdown

ROOT = Path(__file__).resolve().parents[1]
DOCS = ["README.md", "docs/connectors.md", "docs/connectors/README.md"]


@pytest.mark.parametrize("doc", DOCS)
def test_docs_embed_the_generated_matrix(doc):
    text = (ROOT / doc).read_text(encoding="utf-8")
    embedded = text.split(MATRIX_BEGIN, 1)[1].split(MATRIX_END, 1)[0].strip()
    assert embedded == render_matrix_markdown().strip(), f"{doc} is out of date: regenerate the matrix from registry.py"


def test_native_connectors_have_modules_and_builders():
    for c in CONNECTOR_MATRIX:
        if c.status in ("stable", "experimental"):
            assert c.module and (ROOT / "src" / "runport" / c.module).is_file(), c.id
            assert c.id in CONNECTORS.values(), f"{c.id} has no build_target type"
        else:
            assert c.module is None, f"{c.id} is {c.status} and must not claim a module"
        if c.status == "via":
            assert c.via in {x.id for x in CONNECTOR_MATRIX if x.status in ("stable", "experimental")}
        if c.status == "planned":
            assert all(getattr(c, f) == registry.NO for f in ("tested", "streaming", "tool_calls", "per_step_trace")), c.id


def _module_text(c):
    return (ROOT / "src" / "runport" / c.module).read_text(encoding="utf-8")


def test_capability_claims_are_backed_by_code():
    for c in CONNECTOR_MATRIX:
        if not c.module:
            continue
        src = _module_text(c)
        if c.streaming == YES:
            assert re.search(r"text/event-stream|stream", src, re.I) and "streaming" in src, f"{c.id} claims streaming"
        if c.tool_calls == YES:
            assert "tools/call" in src, f"{c.id} claims tool calls"
        if c.structured_output == YES:
            assert "structuredContent" in src or "response_format" in src, f"{c.id} claims structured output"
        if c.per_step_trace in (YES, registry.PARTIAL):
            assert "node" in src or "trajectory" in src, f"{c.id} claims per-step trace"


def test_connector_runtime_capabilities_do_not_overclaim():
    from runport.connectors.ollama import OllamaConnector
    from runport.connectors.openai_compat import OpenAICompatConnector

    assert "streaming" not in OpenAICompatConnector("x", "x", model="m").capabilities
    assert "streaming" not in OllamaConnector("x", "x", model="m").capabilities


def test_every_spec_type_builds(monkeypatch):
    monkeypatch.setenv("DIFY_KEY", "app-test")
    specs = {
        "openrouter": {"type": "openrouter", "model": "google/gemini-3.5-flash-lite"},
        "openai_compat": {"type": "openai_compat", "model": "m", "base_url": "https://api.example.com/v1"},
        "http_workflow": {"type": "http_workflow", "url": "https://wf.example.com"},
        "ollama": {"type": "ollama", "model": "llama3"},
        "dify": {"type": "dify", "api_key": "$DIFY_KEY"},
        "flowise": {"type": "flowise", "base_url": "https://fw.example.com", "flow_id": "f"},
        "langflow": {"type": "langflow", "base_url": "https://lf.example.com", "flow_id": "f"},
        "n8n": {"type": "n8n", "url": "https://n8n.example.com/webhook/x"},
        "langgraph": {"type": "langgraph", "base_url": "https://lg.example.com"},
        "python": {"type": "python", "callable": "json:dumps"},
        "subprocess": {"type": "subprocess", "command": ["cat"]},
        "mcp": {"type": "mcp", "url": "https://mcp.example.com/mcp"},
    }
    assert set(specs) == set(CONNECTORS)
    for name, spec in specs.items():
        t = registry.build_target(name, spec)
        assert t.target_id == name


def test_specs_refuse_literal_credentials_and_local_code_where_disallowed():
    with pytest.raises(registry.TargetSpecError):
        registry.check_spec_has_no_literal_secrets("x", {"type": "openai_compat", "api_key": "sk-literal"})
    with pytest.raises(registry.TargetSpecError):
        registry.check_spec_has_no_literal_secrets("x", {"type": "http_workflow", "headers": {"Authorization": "Bearer abc"}})
    registry.check_spec_has_no_literal_secrets("x", {"type": "http_workflow", "headers": {"Authorization": "Bearer ${TOKEN}"}})
    with pytest.raises(registry.TargetSpecError):
        registry.build_target("x", {"type": "subprocess", "command": ["sh"]}, allow_local_processes=False)
    with pytest.raises(registry.TargetSpecError, match="not set"):
        registry.build_target("x", {"type": "dify", "api_key": "$DEFINITELY_UNSET_VAR_123"})

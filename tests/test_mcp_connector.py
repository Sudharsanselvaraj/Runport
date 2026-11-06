"""Offline tests for the experimental MCP target connector.

The stdio tests launch tests/fixtures/mcp_fixture_server.py as a child process (pipes only). The Streamable
HTTP tests replace urllib.request.urlopen with a scripted fake. Sockets are blocked throughout.
"""

import dataclasses
import email.message
import io
import json
import socket
import sys
import urllib.error
from pathlib import Path

import pytest

from runport.connectors.mcp import McpToolTarget, validate_json_schema
from runport.targets.base import CostBasis, TargetStatus, TargetType

FIXTURE = str(Path(__file__).parent / "fixtures" / "mcp_fixture_server.py")


@pytest.fixture(autouse=True)
def _block_sockets(monkeypatch):
    def deny(*args, **kwargs):
        raise RuntimeError("network access is blocked in MCP connector tests")

    monkeypatch.setattr(socket.socket, "connect", deny)
    monkeypatch.setattr(socket, "create_connection", deny)


@pytest.fixture
def target():
    t = McpToolTarget("mcp-fixture", "Fixture MCP", command=[sys.executable, FIXTURE], timeout_seconds=5.0)
    yield t
    t.close()


def test_discovery_follows_pagination_and_skips_server_messages(target):
    tools = target.discover_tools()
    assert [t["name"] for t in tools] == ["echo", "add", "fail", "hang", "leak"]
    echo = tools[0]
    assert echo["inputSchema"]["required"] == ["text"]
    assert target.target_type == TargetType.MCP_TOOL


def test_successful_call_records_tool_latency_and_unavailable_cost(target):
    first = target.execute({"tool": "echo", "arguments": {"text": "hello"}})
    assert first.status == TargetStatus.SUCCESS
    assert first.output_text == "hello"
    assert first.cost_usd is None and first.cost_basis == CostBasis.UNAVAILABLE
    assert first.tokens_in is None and first.tokens_out is None
    assert first.latency_ms is not None and first.latency_ms == first.metadata["tool_latency_ms"]
    assert first.metadata["session_setup_ms"] is not None  # cold start is recorded apart from tool latency
    assert first.metadata["protocol_version"] == "2025-06-18"
    assert first.metadata["server_info"] == {"name": "fixture", "version": "1.0"}
    assert first.metadata["schema_validation"]["status"] == "passed"

    second = target.execute({"tool": "echo", "arguments": {"text": "again"}})
    assert second.output_text == "again"
    assert second.metadata["session_setup_ms"] is None  # session reused


def test_structured_content_and_arguments_template():
    t = McpToolTarget(
        "mcp-add",
        "Fixture add",
        command=[sys.executable, FIXTURE],
        tool_name="add",
        arguments_template={"a": "{{x}}", "b": "{{y}}"},
    )
    try:
        res = t.execute({"x": 2, "y": 3.5})
    finally:
        t.close()
    assert res.status == TargetStatus.SUCCESS
    assert json.loads(res.output_text) == {"sum": 5.5}


def test_schema_invalid_arguments_are_rejected_before_the_call(target):
    res = target.execute({"tool": "echo", "arguments": {"text": 7, "extra": True}})
    assert res.status == TargetStatus.FAILED
    assert res.error_code == "SCHEMA_INVALID_ARGUMENTS"
    assert res.metadata["schema_validation"]["status"] == "failed"
    assert res.metadata["tool_latency_ms"] is None  # the tool was never called
    assert res.latency_ms is None


def test_schema_record_mode_still_calls_the_tool():
    t = McpToolTarget("m", "m", command=[sys.executable, FIXTURE], validate_arguments="record")
    try:
        res = t.execute({"tool": "echo", "arguments": {"text": "x", "extra": 1}})
    finally:
        t.close()
    assert res.status == TargetStatus.SUCCESS
    assert res.metadata["schema_validation"]["status"] == "failed"


def test_tool_error_is_a_failure_with_scrubbed_message(target):
    res = target.execute({"tool": "fail", "arguments": {}})
    assert res.status == TargetStatus.FAILED
    assert res.error_code == "TOOL_ERROR"
    assert "upstream unavailable" in res.error_message
    assert res.output_text is None
    assert res.cost_basis == CostBasis.UNAVAILABLE and res.cost_usd is None


def test_unknown_tool_is_reported(target):
    res = target.execute({"tool": "does-not-exist", "arguments": {}})
    assert res.status == TargetStatus.FAILED
    assert res.error_code == "UNKNOWN_TOOL"


def test_timeout_tears_down_the_session_and_recovers():
    t = McpToolTarget("m", "m", command=[sys.executable, FIXTURE], timeout_seconds=0.5, init_timeout_seconds=10.0)
    try:
        res = t.execute({"tool": "hang", "arguments": {}})
        assert res.status == TargetStatus.TIMEOUT
        assert res.error_code == "TIMEOUT"
        assert res.latency_ms is not None and res.latency_ms >= 400
        assert res.cost_usd is None and res.cost_basis == CostBasis.UNAVAILABLE
        assert "fixture server starting" in res.metadata.get("server_stderr_tail", "")

        after = t.execute({"tool": "echo", "arguments": {"text": "back"}})
        assert after.status == TargetStatus.SUCCESS
        assert after.metadata["session_setup_ms"] is not None  # a fresh session was opened
    finally:
        t.close()


def test_unsupported_protocol_version_fails_closed():
    t = McpToolTarget("m", "m", command=[sys.executable, FIXTURE, "--bad-version"])
    try:
        res = t.execute({"tool": "echo", "arguments": {"text": "x"}})
    finally:
        t.close()
    assert res.status == TargetStatus.FAILED
    assert res.error_code == "PROTOCOL_ERROR"
    assert "unsupported protocol version" in res.error_message


def test_missing_server_binary_is_a_transport_error():
    t = McpToolTarget("m", "m", command=["/nonexistent/mcp-server-binary"])
    res = t.execute({"tool": "echo", "arguments": {"text": "x"}})
    assert res.status == TargetStatus.FAILED
    assert res.error_code == "TRANSPORT_ERROR"


def test_env_secret_is_scrubbed_from_tool_output():
    import os

    secret = "fixture-secret-value-123"
    env = {**os.environ, "MCP_FIXTURE_SECRET": secret}
    t = McpToolTarget("m", "m", command=[sys.executable, FIXTURE], env={"MCP_FIXTURE_SECRET": secret, "PATH": env.get("PATH", "")})
    try:
        res = t.execute({"tool": "leak", "arguments": {}})
    finally:
        t.close()
    assert res.status == TargetStatus.SUCCESS
    assert secret not in json.dumps(dataclasses.asdict(res), default=str)
    assert "[REDACTED_SECRET]" in res.output_text


def test_constructor_requires_exactly_one_transport():
    with pytest.raises(ValueError):
        McpToolTarget("m", "m")
    with pytest.raises(ValueError):
        McpToolTarget("m", "m", command=["x"], url="https://mcp.example.com/mcp")


def test_schema_validator_reports_unsupported_rules():
    errors, unsupported = validate_json_schema({"a": "x"}, {"type": "object", "properties": {"a": {"type": "string"}}, "dependentRequired": {}})
    assert errors == []
    assert unsupported == ["dependentRequired"]
    errors, _ = validate_json_schema({"n": 3}, {"type": "object", "properties": {"n": {"type": "integer", "maximum": 2}}})
    assert errors and "maximum" in errors[0]


# --------------------------------------------------------------------------------------------------
# Streamable HTTP (scripted fake urlopen)
# --------------------------------------------------------------------------------------------------

TOKEN = "mcp-http-token-abcdef123456"


class FakeResponse:
    def __init__(self, body: bytes, content_type: str = "application/json", headers: dict | None = None):
        self._buf = io.BytesIO(body)
        self.headers = email.message.Message()
        self.headers["Content-Type"] = content_type
        for k, v in (headers or {}).items():
            self.headers[k] = v

    def read(self, *a):
        return self._buf.read(*a)

    def readline(self):
        return self._buf.readline()

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class ScriptedServer:
    def __init__(self):
        self.requests = []

    def __call__(self, req, timeout=None):
        headers = {k.lower(): v for k, v in req.header_items()}
        body = json.loads(req.data) if req.data else None
        self.requests.append((req.get_method(), headers, body))
        if req.get_method() == "DELETE":
            return FakeResponse(b"")
        method = body.get("method")
        if "id" not in body:
            return FakeResponse(b"", headers={})
        rid = body["id"]
        if method == "initialize":
            res = {"protocolVersion": "2025-03-26", "capabilities": {"tools": {"listChanged": True}}, "serverInfo": {"name": "http-fixture"}}
            return FakeResponse(json.dumps({"jsonrpc": "2.0", "id": rid, "result": res}).encode(), headers={"Mcp-Session-Id": "sess-1"})
        if method == "tools/list":
            tools = [{"name": "lookup", "inputSchema": {"type": "object", "properties": {"q": {"type": "string"}}, "required": ["q"]}}]
            sse = (
                ": keep-alive\n\n"
                'data: {"jsonrpc":"2.0","method":"notifications/progress","params":{}}\n\n'
                f"event: message\ndata: {json.dumps({'jsonrpc': '2.0', 'id': rid, 'result': {'tools': tools}})}\n\n"
            )
            return FakeResponse(sse.encode(), content_type="text/event-stream")
        if method == "tools/call":
            q = body["params"]["arguments"]["q"]
            if q == "boom":
                raise urllib.error.HTTPError(req.full_url, 500, "err", email.message.Message(), io.BytesIO(f"bad Authorization: Bearer {TOKEN}".encode()))
            if q == "rpc":
                return FakeResponse(json.dumps({"jsonrpc": "2.0", "id": rid, "error": {"code": -32603, "message": "internal"}}).encode())
            return FakeResponse(json.dumps({"jsonrpc": "2.0", "id": rid, "result": {"content": [{"type": "text", "text": f"found {q}"}]}}).encode())
        raise AssertionError(method)


def _http_target(monkeypatch):
    server = ScriptedServer()
    monkeypatch.setattr("urllib.request.urlopen", server)
    t = McpToolTarget("mcp-http", "HTTP MCP", url="https://mcp.example.com/mcp", headers={"Authorization": f"Bearer {TOKEN}"}, tool_name="lookup")
    return t, server


def test_http_session_headers_sse_and_close(monkeypatch):
    t, server = _http_target(monkeypatch)
    res = t.execute({"q": "runport"})
    assert res.status == TargetStatus.SUCCESS
    assert res.output_text == "found runport"
    assert res.metadata["transport"] == "streamable_http"
    assert res.metadata["protocol_version"] == "2025-03-26"
    assert res.cost_basis == CostBasis.UNAVAILABLE and res.cost_usd is None

    methods = [(m, b.get("method") if b else None) for m, _, b in server.requests]
    assert methods[:4] == [("POST", "initialize"), ("POST", "notifications/initialized"), ("POST", "tools/list"), ("POST", "tools/call")]
    call_headers = server.requests[3][1]
    assert call_headers["mcp-session-id"] == "sess-1"
    assert call_headers["mcp-protocol-version"] == "2025-03-26"
    assert "text/event-stream" in call_headers["accept"]

    t.close()
    assert server.requests[-1][0] == "DELETE"
    assert TOKEN not in json.dumps(dataclasses.asdict(res), default=str)


def test_http_errors_are_scrubbed_and_rpc_errors_mapped(monkeypatch):
    t, _ = _http_target(monkeypatch)
    try:
        boom = t.execute({"q": "boom"})
        assert boom.status == TargetStatus.FAILED
        assert boom.error_code == "HTTP_500"
        assert TOKEN not in boom.error_message
        assert TOKEN not in json.dumps(dataclasses.asdict(boom), default=str)

        rpc = t.execute({"q": "rpc"})
        assert rpc.status == TargetStatus.FAILED
        assert rpc.error_code == "JSONRPC_-32603"
    finally:
        t.close()


def test_http_url_is_ssrf_checked():
    from runport.core.security import SSRFSecurityError

    with pytest.raises(SSRFSecurityError):
        McpToolTarget("m", "m", url="http://169.254.169.254/mcp")

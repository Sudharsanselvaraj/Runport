"""Model Context Protocol (MCP) target connector for Runport (experimental).

Benchmarks the tools of an existing MCP server. Each benchmark case selects a tool and its
arguments; the connector speaks JSON-RPC 2.0 MCP directly (no SDK dependency):

    initialize (capability negotiation) -> notifications/initialized -> tools/list -> tools/call ... -> close

Transports:
    * stdio: launches a local server process and exchanges newline-delimited JSON-RPC messages.
    * Streamable HTTP: POSTs JSON-RPC messages to a single endpoint; responses arrive as JSON or SSE.

Invariants honoured here (see AGENTS.md):
    * Null is not 0: MCP tool calls carry no price and no token usage, so cost stays ``None`` with
      provenance ``UNAVAILABLE`` and tokens stay ``None``.
    * Secret scrubbing: configured header values and env values are never written to results; every
      string that leaves the connector (errors, server stderr, tool output) is scrubbed first.
    * The connector is only the transport step of the runner's guard order; authorization, privacy,
      budget preflight and spend booking stay with the runner. Tool calls are never retried, because
      a tool may have side effects.
"""

from __future__ import annotations

import json
import queue
import re
import subprocess
import threading
import time
import urllib.error
import urllib.request
from collections import deque
from typing import IO, Any, Callable, Deque, Dict, List, Optional, Tuple

from runport import __version__
from runport.core.security import validate_safe_url
from runport.providers.base import scrub_secrets
from runport.targets.base import BillingMode, CostBasis, Target, TargetResult, TargetStatus, TargetType, billing_for_url

LATEST_PROTOCOL_VERSION = "2025-06-18"
SUPPORTED_PROTOCOL_VERSIONS = ("2025-06-18", "2025-03-26", "2024-11-05")
CLIENT_INFO = {"name": "runport", "version": __version__}
_STDERR_TAIL_LINES = 20
_SENSITIVE_ENV_NAME = re.compile(r"KEY|TOKEN|SECRET|PASS|AUTH|CREDENTIAL|COOKIE|PRIVATE", re.IGNORECASE)
_REDACTED = "[REDACTED_SECRET]"


class McpError(Exception):
    """Base error for MCP sessions. ``code`` is a stable error code for TargetResult.error_code."""

    code = "PROTOCOL_ERROR"


class McpProtocolError(McpError):
    """The peer broke the protocol: malformed JSON, missing fields, process exit, unsupported version."""

    code = "PROTOCOL_ERROR"


class McpTimeoutError(McpError):
    """A request did not receive its response within the deadline."""

    code = "TIMEOUT"


class McpRpcError(McpError):
    """The server answered a request with a JSON-RPC error object."""

    def __init__(self, rpc_code: Optional[int], message: str, data: Any = None) -> None:
        super().__init__(message)
        self.rpc_code = rpc_code
        self.data = data
        self.code = f"JSONRPC_{rpc_code}" if rpc_code is not None else "JSONRPC_ERROR"


class McpTransportError(McpError):
    """The transport failed (connection refused, HTTP error status, process could not start)."""

    def __init__(self, message: str, status: Optional[int] = None) -> None:
        super().__init__(message)
        self.status = status
        self.code = f"HTTP_{status}" if status is not None else "TRANSPORT_ERROR"


# --------------------------------------------------------------------------------------------------
# Minimal JSON Schema validator (the subset MCP tool inputSchemas use in practice)
# --------------------------------------------------------------------------------------------------

_SUPPORTED_KEYWORDS = frozenset(
    {
        "type",
        "properties",
        "required",
        "additionalProperties",
        "items",
        "enum",
        "const",
        "minimum",
        "maximum",
        "exclusiveMinimum",
        "exclusiveMaximum",
        "minLength",
        "maxLength",
        "pattern",
        "minItems",
        "maxItems",
        "anyOf",
        "oneOf",
        "allOf",
        "not",
    }
)
# Annotation keywords that never affect validity.
_ANNOTATION_KEYWORDS = frozenset(
    {"$schema", "$id", "$comment", "title", "description", "default", "examples", "format", "readOnly", "writeOnly", "deprecated", "$defs", "definitions"}
)


def _type_matches(value: Any, expected: str) -> bool:
    if expected == "null":
        return value is None
    if expected == "boolean":
        return isinstance(value, bool)
    if expected == "integer":
        return (isinstance(value, int) and not isinstance(value, bool)) or (isinstance(value, float) and value.is_integer())
    if expected == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if expected == "string":
        return isinstance(value, str)
    if expected == "array":
        return isinstance(value, list)
    if expected == "object":
        return isinstance(value, dict)
    return True  # unknown type names are not enforced


def validate_json_schema(value: Any, schema: Any) -> Tuple[List[str], List[str]]:
    """Validates ``value`` against a JSON Schema subset.

    Returns ``(errors, unsupported_keywords)``. Keywords outside the supported subset are reported,
    not silently treated as satisfied, so a "passed" result is never stronger than it really is.
    """
    errors: List[str] = []
    unsupported: set[str] = set()
    _validate(value, schema, "$", errors, unsupported)
    return errors, sorted(unsupported)


def _validate(value: Any, schema: Any, path: str, errors: List[str], unsupported: set[str]) -> None:
    if schema is True or schema is None:
        return
    if schema is False:
        errors.append(f"{path}: no value is allowed here")
        return
    if not isinstance(schema, dict):
        return

    for key in schema:
        if key not in _SUPPORTED_KEYWORDS and key not in _ANNOTATION_KEYWORDS:
            unsupported.add(key)

    expected = schema.get("type")
    if expected is not None:
        types = expected if isinstance(expected, list) else [expected]
        if not any(_type_matches(value, str(t)) for t in types):
            errors.append(f"{path}: expected type {'/'.join(str(t) for t in types)}, got {type(value).__name__}")
            return

    if "enum" in schema and isinstance(schema["enum"], list) and value not in schema["enum"]:
        errors.append(f"{path}: value is not one of the allowed enum values")
    if "const" in schema and value != schema["const"]:
        errors.append(f"{path}: value does not equal the required const")

    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if isinstance(schema.get("minimum"), (int, float)) and value < schema["minimum"]:
            errors.append(f"{path}: {value} is below minimum {schema['minimum']}")
        if isinstance(schema.get("maximum"), (int, float)) and value > schema["maximum"]:
            errors.append(f"{path}: {value} is above maximum {schema['maximum']}")
        if isinstance(schema.get("exclusiveMinimum"), (int, float)) and value <= schema["exclusiveMinimum"]:
            errors.append(f"{path}: {value} must be greater than {schema['exclusiveMinimum']}")
        if isinstance(schema.get("exclusiveMaximum"), (int, float)) and value >= schema["exclusiveMaximum"]:
            errors.append(f"{path}: {value} must be less than {schema['exclusiveMaximum']}")

    if isinstance(value, str):
        if isinstance(schema.get("minLength"), int) and len(value) < schema["minLength"]:
            errors.append(f"{path}: string shorter than minLength {schema['minLength']}")
        if isinstance(schema.get("maxLength"), int) and len(value) > schema["maxLength"]:
            errors.append(f"{path}: string longer than maxLength {schema['maxLength']}")
        if isinstance(schema.get("pattern"), str):
            try:
                if re.search(schema["pattern"], value) is None:
                    errors.append(f"{path}: string does not match pattern")
            except re.error:
                unsupported.add("pattern")

    if isinstance(value, list):
        if isinstance(schema.get("minItems"), int) and len(value) < schema["minItems"]:
            errors.append(f"{path}: fewer than minItems {schema['minItems']}")
        if isinstance(schema.get("maxItems"), int) and len(value) > schema["maxItems"]:
            errors.append(f"{path}: more than maxItems {schema['maxItems']}")
        items = schema.get("items")
        if isinstance(items, (dict, bool)):
            for i, item in enumerate(value):
                _validate(item, items, f"{path}[{i}]", errors, unsupported)
        elif isinstance(items, list):
            unsupported.add("items(tuple)")

    if isinstance(value, dict):
        raw_props = schema.get("properties")
        props: Dict[str, Any] = raw_props if isinstance(raw_props, dict) else {}
        raw_required = schema.get("required")
        required: List[Any] = raw_required if isinstance(raw_required, list) else []
        for name in required:
            if name not in value:
                errors.append(f"{path}: missing required property '{name}'")
        additional = schema.get("additionalProperties", True)
        for name, item in value.items():
            if name in props:
                _validate(item, props[name], f"{path}.{name}", errors, unsupported)
            elif additional is False:
                errors.append(f"{path}: unexpected property '{name}'")
            elif isinstance(additional, dict):
                _validate(item, additional, f"{path}.{name}", errors, unsupported)

    for sub_key in ("allOf",):
        for sub in schema.get(sub_key) or []:
            _validate(value, sub, path, errors, unsupported)
    if isinstance(schema.get("anyOf"), list):
        branches = [_branch_errors(value, s, path, unsupported) for s in schema["anyOf"]]
        if branches and all(branches):
            errors.append(f"{path}: value matches none of anyOf")
    if isinstance(schema.get("oneOf"), list):
        matches = sum(1 for s in schema["oneOf"] if not _branch_errors(value, s, path, unsupported))
        if matches != 1:
            errors.append(f"{path}: value matches {matches} of oneOf (exactly 1 required)")
    if "not" in schema and not _branch_errors(value, schema["not"], path, unsupported):
        errors.append(f"{path}: value must not match the 'not' schema")


def _branch_errors(value: Any, schema: Any, path: str, unsupported: set[str]) -> List[str]:
    errs: List[str] = []
    _validate(value, schema, path, errs, unsupported)
    return errs


# --------------------------------------------------------------------------------------------------
# Transports
# --------------------------------------------------------------------------------------------------


class _Transport:
    """A bidirectional JSON-RPC message channel."""

    name = "abstract"

    def request(self, message: Dict[str, Any], timeout: float) -> Dict[str, Any]:
        raise NotImplementedError

    def notify(self, message: Dict[str, Any]) -> None:
        raise NotImplementedError

    def set_protocol_version(self, version: str) -> None:
        pass

    def close(self) -> None:
        raise NotImplementedError

    def diagnostics(self) -> Optional[str]:
        return None


class StdioTransport(_Transport):
    """Runs an MCP server as a child process; messages are newline-delimited JSON over stdin/stdout."""

    name = "stdio"

    def __init__(
        self,
        command: List[str],
        env: Optional[Dict[str, str]] = None,
        cwd: Optional[str] = None,
        redact: Callable[[str], str] = lambda s: s,
    ) -> None:
        self._redact = redact
        try:
            self._proc = subprocess.Popen(
                command,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=env,
                cwd=cwd,
                bufsize=0,
            )
        except (OSError, ValueError) as e:
            raise McpTransportError(f"could not start MCP server process: {redact(str(e))}") from e
        self._inbox: "queue.Queue[Optional[bytes]]" = queue.Queue()
        self._stderr_tail: Deque[str] = deque(maxlen=_STDERR_TAIL_LINES)
        self._write_lock = threading.Lock()
        assert self._proc.stdout is not None and self._proc.stderr is not None
        threading.Thread(target=self._pump_stdout, args=(self._proc.stdout,), daemon=True).start()
        threading.Thread(target=self._pump_stderr, args=(self._proc.stderr,), daemon=True).start()

    def _pump_stdout(self, stream: IO[bytes]) -> None:
        try:
            for line in iter(stream.readline, b""):
                if line.strip():
                    self._inbox.put(line)
        except (OSError, ValueError):
            pass
        finally:
            self._inbox.put(None)  # EOF sentinel

    def _pump_stderr(self, stream: IO[bytes]) -> None:
        try:
            for line in iter(stream.readline, b""):
                self._stderr_tail.append(line.decode("utf-8", errors="replace").rstrip())
        except (OSError, ValueError):
            pass

    def _send(self, message: Dict[str, Any]) -> None:
        data = (json.dumps(message, separators=(",", ":")) + "\n").encode("utf-8")
        stdin = self._proc.stdin
        if stdin is None:
            raise McpProtocolError("MCP server stdin is closed")
        with self._write_lock:
            try:
                stdin.write(data)
                stdin.flush()
            except (BrokenPipeError, OSError, ValueError) as e:
                raise McpProtocolError(f"MCP server process is not accepting input (exit code {self._proc.poll()})") from e

    def notify(self, message: Dict[str, Any]) -> None:
        self._send(message)

    def request(self, message: Dict[str, Any], timeout: float) -> Dict[str, Any]:
        self._send(message)
        deadline = time.monotonic() + timeout
        want = message["id"]
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise McpTimeoutError(f"no response to '{message.get('method')}' within {timeout}s")
            try:
                line = self._inbox.get(timeout=remaining)
            except queue.Empty:
                raise McpTimeoutError(f"no response to '{message.get('method')}' within {timeout}s") from None
            if line is None:
                self._inbox.put(None)  # keep EOF visible to later reads
                code = self._proc.poll()
                raise McpProtocolError(f"MCP server closed stdout before responding (exit code {code})")
            reply = _handle_incoming(line, want, self._send)
            if reply is not None:
                return reply

    def close(self) -> None:
        proc = self._proc
        if proc.poll() is None:
            try:
                if proc.stdin is not None:
                    proc.stdin.close()
            except OSError:
                pass
            for step in (proc.terminate, proc.kill):
                try:
                    proc.wait(timeout=1.0)
                    break
                except subprocess.TimeoutExpired:
                    step()
            try:
                proc.wait(timeout=1.0)
            except subprocess.TimeoutExpired:
                pass
        for stream in (proc.stdout, proc.stderr):
            try:
                if stream is not None:
                    stream.close()
            except OSError:
                pass

    def diagnostics(self) -> Optional[str]:
        if not self._stderr_tail:
            return None
        return scrub_secrets(self._redact("\n".join(self._stderr_tail)))


def _handle_incoming(raw: bytes, want_id: Any, send: Callable[[Dict[str, Any]], None]) -> Optional[Dict[str, Any]]:
    """Processes one incoming message. Returns it when it is the response to ``want_id``.

    Notifications are ignored. Requests from the server are answered: ``ping`` with an empty result,
    anything else with "method not found" (this client advertises no client capabilities).
    """
    try:
        msg = json.loads(raw)
    except (ValueError, UnicodeDecodeError) as e:
        raise McpProtocolError("MCP server sent a message that is not valid JSON") from e
    if isinstance(msg, list):
        for item in msg:
            reply = _handle_incoming(json.dumps(item).encode("utf-8"), want_id, send)
            if reply is not None:
                return reply
        return None
    if not isinstance(msg, dict) or msg.get("jsonrpc") != "2.0":
        raise McpProtocolError("MCP server sent a message that is not a JSON-RPC 2.0 object")
    if "method" in msg:
        if "id" in msg:  # server -> client request
            if msg["method"] == "ping":
                send({"jsonrpc": "2.0", "id": msg["id"], "result": {}})
            else:
                send({"jsonrpc": "2.0", "id": msg["id"], "error": {"code": -32601, "message": "Method not found"}})
        return None
    if msg.get("id") == want_id:
        if "result" not in msg and "error" not in msg:
            raise McpProtocolError("JSON-RPC response has neither 'result' nor 'error'")
        return msg
    return None  # a stale response to an earlier (timed-out) request


class StreamableHttpTransport(_Transport):
    """MCP Streamable HTTP: every message is POSTed to one endpoint; replies are JSON or an SSE stream.

    Header values are kept private to the transport and redacted from every error message.
    """

    name = "streamable_http"

    def __init__(self, url: str, headers: Optional[Dict[str, str]] = None, redact: Callable[[str], str] = lambda s: s) -> None:
        self.url = url
        self._headers = dict(headers or {})
        self._redact = redact
        self._session_id: Optional[str] = None
        self._protocol_version: Optional[str] = None

    def set_protocol_version(self, version: str) -> None:
        self._protocol_version = version

    def _request_headers(self) -> Dict[str, str]:
        h = {"Content-Type": "application/json", "Accept": "application/json, text/event-stream", **self._headers}
        if self._session_id:
            h["Mcp-Session-Id"] = self._session_id
        if self._protocol_version:
            h["MCP-Protocol-Version"] = self._protocol_version
        return h

    def _open(self, method: str, body: Optional[bytes], timeout: float) -> Any:
        req = urllib.request.Request(self.url, data=body, headers=self._request_headers(), method=method)
        try:
            return urllib.request.urlopen(req, timeout=timeout)
        except urllib.error.HTTPError as e:
            try:
                detail = e.read().decode("utf-8", errors="replace")[:500]
            except Exception:
                detail = ""
            if e.code == 404 and self._session_id:
                detail = "session expired or unknown (404)"
            raise McpTransportError(f"MCP HTTP error {e.code}: {scrub_secrets(self._redact(detail))}", status=e.code) from e
        except (TimeoutError, urllib.error.URLError, ConnectionError, OSError) as e:
            reason = getattr(e, "reason", e)
            if isinstance(e, TimeoutError) or isinstance(reason, TimeoutError):
                raise McpTimeoutError(f"MCP HTTP request timed out after {timeout}s") from e
            raise McpTransportError(f"MCP HTTP transport failed: {scrub_secrets(self._redact(str(reason)))}") from e

    def notify(self, message: Dict[str, Any]) -> None:
        with self._open("POST", json.dumps(message).encode("utf-8"), timeout=10.0) as resp:
            resp.read()

    def request(self, message: Dict[str, Any], timeout: float) -> Dict[str, Any]:
        deadline = time.monotonic() + timeout
        want = message["id"]
        try:
            resp_cm = self._open("POST", json.dumps(message).encode("utf-8"), timeout=timeout)
            with resp_cm as resp:
                headers = getattr(resp, "headers", None)
                sid = headers.get("Mcp-Session-Id") if headers is not None else None
                if sid and message.get("method") == "initialize":
                    self._session_id = str(sid)
                ctype = (headers.get("Content-Type") if headers is not None else None) or "application/json"
                if "text/event-stream" in ctype.lower():
                    return self._read_sse(resp, want, deadline, timeout, message)
                body = resp.read()
                if not body:
                    raise McpProtocolError("MCP HTTP response body is empty")
                reply = _handle_incoming(body, want, self._post_reply)
                if reply is None:
                    raise McpProtocolError("MCP HTTP response did not contain the matching JSON-RPC response")
                return reply
        except TimeoutError as e:
            raise McpTimeoutError(f"no response to '{message.get('method')}' within {timeout}s") from e

    def _post_reply(self, message: Dict[str, Any]) -> None:
        self.notify(message)

    def _read_sse(self, resp: Any, want: Any, deadline: float, timeout: float, message: Dict[str, Any]) -> Dict[str, Any]:
        data_lines: List[str] = []
        while True:
            if time.monotonic() > deadline:
                raise McpTimeoutError(f"no response to '{message.get('method')}' within {timeout}s")
            raw = resp.readline()
            if not raw:
                raise McpProtocolError("SSE stream ended before the JSON-RPC response arrived")
            line = raw.decode("utf-8", errors="replace").rstrip("\r\n")
            if line == "":
                if data_lines:
                    payload = "\n".join(data_lines).encode("utf-8")
                    data_lines = []
                    reply = _handle_incoming(payload, want, self._post_reply)
                    if reply is not None:
                        return reply
                continue
            if line.startswith(":"):
                continue
            field, _, val = line.partition(":")
            if field == "data":
                data_lines.append(val[1:] if val.startswith(" ") else val)

    def close(self) -> None:
        if not self._session_id:
            return
        try:
            with self._open("DELETE", None, timeout=5.0) as resp:
                resp.read()
        except McpError:
            pass  # servers may answer 405 when they do not allow client-initiated termination
        finally:
            self._session_id = None


# --------------------------------------------------------------------------------------------------
# Session
# --------------------------------------------------------------------------------------------------


class McpSession:
    """One initialized MCP session over a transport."""

    def __init__(self, transport: _Transport, request_timeout: float, init_timeout: float) -> None:
        self.transport = transport
        self.request_timeout = request_timeout
        self.init_timeout = init_timeout
        self._next_id = 0
        self.protocol_version: Optional[str] = None
        self.server_info: Dict[str, Any] = {}
        self.server_capabilities: Dict[str, Any] = {}

    def _call(self, method: str, params: Optional[Dict[str, Any]] = None, timeout: Optional[float] = None) -> Any:
        self._next_id += 1
        msg: Dict[str, Any] = {"jsonrpc": "2.0", "id": self._next_id, "method": method}
        if params is not None:
            msg["params"] = params
        reply = self.transport.request(msg, self.request_timeout if timeout is None else timeout)
        if "error" in reply:
            err = reply["error"] if isinstance(reply["error"], dict) else {}
            code = err.get("code") if isinstance(err.get("code"), int) else None
            raise McpRpcError(code, scrub_secrets(str(err.get("message", "JSON-RPC error"))), scrub_secrets(err.get("data")))
        return reply.get("result")

    def initialize(self) -> None:
        result = self._call(
            "initialize",
            {"protocolVersion": LATEST_PROTOCOL_VERSION, "capabilities": {}, "clientInfo": CLIENT_INFO},
            timeout=self.init_timeout,
        )
        if not isinstance(result, dict):
            raise McpProtocolError("initialize result is not an object")
        version = result.get("protocolVersion")
        if version not in SUPPORTED_PROTOCOL_VERSIONS:
            raise McpProtocolError(f"server negotiated unsupported protocol version {version!r}")
        caps = result.get("capabilities")
        if not isinstance(caps, dict) or "tools" not in caps:
            raise McpProtocolError("server does not advertise the 'tools' capability")
        self.protocol_version = str(version)
        self.server_capabilities = caps
        info = result.get("serverInfo")
        self.server_info = {k: info.get(k) for k in ("name", "version") if isinstance(info, dict) and k in info}
        self.transport.set_protocol_version(self.protocol_version)
        self.transport.notify({"jsonrpc": "2.0", "method": "notifications/initialized"})

    def list_tools(self) -> List[Dict[str, Any]]:
        tools: List[Dict[str, Any]] = []
        cursor: Optional[str] = None
        for _ in range(100):  # bounded pagination
            result = self._call("tools/list", {"cursor": cursor} if cursor else {})
            if not isinstance(result, dict) or not isinstance(result.get("tools"), list):
                raise McpProtocolError("tools/list result has no 'tools' array")
            tools.extend(t for t in result["tools"] if isinstance(t, dict) and isinstance(t.get("name"), str))
            nxt = result.get("nextCursor")
            if not nxt:
                return tools
            cursor = str(nxt)
        raise McpProtocolError("tools/list pagination did not terminate")

    def call_tool(self, name: str, arguments: Dict[str, Any], timeout: Optional[float] = None) -> Dict[str, Any]:
        request_id = self._next_id + 1
        try:
            result = self._call("tools/call", {"name": name, "arguments": arguments}, timeout=timeout)
        except McpTimeoutError:
            try:
                self.transport.notify({"jsonrpc": "2.0", "method": "notifications/cancelled", "params": {"requestId": request_id, "reason": "client timeout"}})
            except McpError:
                pass
            raise
        if not isinstance(result, dict):
            raise McpProtocolError("tools/call result is not an object")
        return result

    def close(self) -> None:
        self.transport.close()


# --------------------------------------------------------------------------------------------------
# Target
# --------------------------------------------------------------------------------------------------


def _render(template: Any, values: Dict[str, Any]) -> Any:
    """Substitutes ``{{key}}`` placeholders. A string that is exactly one placeholder keeps the value's type."""
    if isinstance(template, str):
        whole = re.fullmatch(r"\{\{\s*([A-Za-z0-9_.\-]+)\s*\}\}", template)
        if whole and whole.group(1) in values:
            return values[whole.group(1)]

        def sub(m: "re.Match[str]") -> str:
            key = m.group(1)
            return str(values[key]) if key in values else m.group(0)

        return re.sub(r"\{\{\s*([A-Za-z0-9_.\-]+)\s*\}\}", sub, template)
    if isinstance(template, dict):
        return {k: _render(v, values) for k, v in template.items()}
    if isinstance(template, list):
        return [_render(v, values) for v in template]
    return template


class McpToolTarget(Target):
    """Benchmarks the tools of an MCP server (experimental).

    Exactly one of ``command`` (stdio) or ``url`` (Streamable HTTP) must be given. The session is opened
    lazily on the first case and reused across cases; ``session_setup_ms`` is recorded on the case that
    opened it so cold start never inflates tool latency. After a timeout or protocol error the session
    is torn down and the next case starts a fresh one.

    A case selects its tool with ``case["tool"]`` (falling back to ``tool_name``) and its arguments with
    ``case["arguments"]`` (falling back to ``arguments_template`` rendered with the case's fields, and
    finally the case's remaining fields).
    """

    def __init__(
        self,
        target_id: str,
        name: str,
        *,
        command: Optional[List[str]] = None,
        env: Optional[Dict[str, str]] = None,
        cwd: Optional[str] = None,
        url: Optional[str] = None,
        headers: Optional[Dict[str, str]] = None,
        tool_name: Optional[str] = None,
        arguments_template: Optional[Dict[str, Any]] = None,
        validate_arguments: str = "enforce",
        timeout_seconds: float = 30.0,
        init_timeout_seconds: Optional[float] = None,
        allow_private: bool = False,
        allow_localhost: bool = False,
        host_allowlist: Optional[List[str]] = None,
        billing: Optional[BillingMode] = None,
    ) -> None:
        if (command is None) == (url is None):
            raise ValueError("McpToolTarget needs exactly one of 'command' (stdio) or 'url' (Streamable HTTP)")
        if command is not None and (not isinstance(command, list) or not command):
            raise ValueError("'command' must be a non-empty argument list")
        if validate_arguments not in ("enforce", "record", "off"):
            raise ValueError("validate_arguments must be 'enforce', 'record' or 'off'")
        super().__init__(
            target_id=target_id,
            name=name,
            target_type=TargetType.MCP_TOOL,
            capabilities=["mcp", "tools", "json"],
            pricing=None,
            timeout_seconds=timeout_seconds,
            max_retries=1,  # tool calls may have side effects: never retried
        )
        self.url = validate_safe_url(url, allow_private=allow_private, allow_localhost=allow_localhost, host_allowlist=host_allowlist) if url else None
        self.command = list(command) if command else None
        # A stdio server is a local process; an HTTP server is billable unless it is on loopback or declared free.
        self.billing = BillingMode(billing) if billing is not None else (BillingMode.LOCAL if command else billing_for_url(self.url))
        self._env = env
        self._cwd = cwd
        self._headers = dict(headers or {})
        self.tool_name = tool_name
        self.arguments_template = arguments_template
        self.validate_arguments = validate_arguments
        self.init_timeout_seconds = init_timeout_seconds if init_timeout_seconds is not None else timeout_seconds
        self.transport_name = StdioTransport.name if command else StreamableHttpTransport.name
        # Values that must never appear in results: every header value, and env values whose variable name looks like a
        # credential. (Redacting every env value would also rewrite ordinary words such as "true" or a PATH entry.)
        sensitive_env = [v for k, v in (env or {}).items() if _SENSITIVE_ENV_NAME.search(k)]
        self._secrets = sorted({v for v in [*self._headers.values(), *sensitive_env] if isinstance(v, str) and len(v) >= 4}, key=len, reverse=True)
        self._session: Optional[McpSession] = None
        self._tools: Dict[str, Dict[str, Any]] = {}
        self._lock = threading.Lock()

    # -- secrets ---------------------------------------------------------------------------------

    def _redact(self, text: str) -> str:
        for secret in self._secrets:
            text = text.replace(secret, _REDACTED)
        return text

    def _clean(self, data: Any) -> Any:
        """Scrubs configured secret values and generic secret patterns from any outgoing data."""
        if isinstance(data, str):
            return scrub_secrets(self._redact(data))
        if isinstance(data, dict):
            return scrub_secrets({k: self._clean(v) for k, v in data.items()})
        if isinstance(data, list):
            return [self._clean(v) for v in data]
        return data

    def _clean_strings(self, data: Any) -> Any:
        """Like _clean, but keeps dict keys intact (tool schemas legitimately name fields like 'api_key')."""
        if isinstance(data, str):
            return scrub_secrets(self._redact(data))
        if isinstance(data, dict):
            return {k: self._clean_strings(v) for k, v in data.items()}
        if isinstance(data, list):
            return [self._clean_strings(v) for v in data]
        return data

    # -- session lifecycle -----------------------------------------------------------------------

    def _make_transport(self) -> _Transport:
        if self.command is not None:
            return StdioTransport(self.command, env=self._env, cwd=self._cwd, redact=self._redact)
        assert self.url is not None
        return StreamableHttpTransport(self.url, headers=self._headers, redact=self._redact)

    def _ensure_session(self) -> Tuple[McpSession, Optional[float]]:
        if self._session is not None:
            return self._session, None
        started = time.perf_counter()
        session = McpSession(self._make_transport(), self.timeout_seconds, self.init_timeout_seconds)
        try:
            session.initialize()
            tools = session.list_tools()
        except BaseException:
            session.close()
            raise
        self._session = session
        self._tools = {t["name"]: t for t in tools}
        return session, (time.perf_counter() - started) * 1000.0

    def _drop_session(self) -> Optional[str]:
        session, self._session = self._session, None
        self._tools = {}
        if session is None:
            return None
        diag = session.transport.diagnostics()
        session.close()
        return diag

    def discover_tools(self) -> List[Dict[str, Any]]:
        """Opens (or reuses) the session and returns the discovered tools, scrubbed."""
        with self._lock:
            self._ensure_session()
            return [self._clean_strings(t) for t in self._tools.values()]

    def close(self) -> None:
        """Ends the session (stdin close + terminate for stdio, DELETE for HTTP)."""
        with self._lock:
            self._drop_session()

    def __enter__(self) -> "McpToolTarget":
        return self

    def __exit__(self, *exc: Any) -> None:
        self.close()

    def __del__(self) -> None:
        try:
            if self._session is not None:
                self._session.close()
        except Exception:
            pass

    # -- execution -------------------------------------------------------------------------------

    def _select(self, input_payload: Dict[str, Any]) -> Tuple[Optional[str], Any]:
        tool = input_payload.get("tool") or self.tool_name
        if "arguments" in input_payload:
            args = input_payload["arguments"]
        elif self.arguments_template is not None:
            args = _render(self.arguments_template, input_payload)
        else:
            args = {k: v for k, v in input_payload.items() if k != "tool"}
        return (str(tool) if tool else None), args

    def _fail(
        self,
        status: TargetStatus,
        code: str,
        message: str,
        metadata: Dict[str, Any],
        latency_ms: Optional[float] = None,
    ) -> TargetResult:
        return TargetResult(
            target_id=self.target_id,
            status=status,
            latency_ms=latency_ms,
            cost_usd=None,
            cost_basis=CostBasis.UNAVAILABLE,
            error_code=code,
            error_message=self._clean(message),
            metadata=self._clean(metadata),
        )

    def execute(self, input_payload: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> TargetResult:
        tool, arguments = self._select(input_payload)
        meta: Dict[str, Any] = {
            "transport": self.transport_name,
            "tool": tool,
            "session_setup_ms": None,
            "tool_latency_ms": None,
            "protocol_version": None,
            "server_info": None,
            "schema_validation": {"status": "skipped", "errors": [], "unsupported_rules": []},
        }
        if not tool:
            return self._fail(TargetStatus.FAILED, "NO_TOOL_SELECTED", "case selects no tool and the target has no default tool_name", meta)
        if not isinstance(arguments, dict):
            return self._fail(TargetStatus.FAILED, "INVALID_ARGUMENTS", "tool arguments must be a JSON object", meta)

        with self._lock:
            try:
                session, setup_ms = self._ensure_session()
            except McpError as e:
                diag = self._drop_session()
                if diag:
                    meta["server_stderr_tail"] = diag
                status = TargetStatus.TIMEOUT if isinstance(e, McpTimeoutError) else TargetStatus.FAILED
                return self._fail(status, e.code, f"MCP session setup failed: {e}", meta)
            meta["session_setup_ms"] = setup_ms
            meta["protocol_version"] = session.protocol_version
            meta["server_info"] = session.server_info or None

            spec = self._tools.get(tool)
            if spec is None:
                return self._fail(TargetStatus.FAILED, "UNKNOWN_TOOL", f"server does not list a tool named '{tool}'", meta)

            if self.validate_arguments != "off":
                schema = spec.get("inputSchema")
                if isinstance(schema, dict):
                    errors, unsupported = validate_json_schema(arguments, schema)
                    meta["schema_validation"] = {"status": "failed" if errors else "passed", "errors": errors, "unsupported_rules": unsupported}
                    if errors and self.validate_arguments == "enforce":
                        return self._fail(
                            TargetStatus.FAILED,
                            "SCHEMA_INVALID_ARGUMENTS",
                            "arguments do not match the tool's inputSchema: " + "; ".join(errors[:5]),
                            meta,
                        )
                else:
                    meta["schema_validation"] = {"status": "no_schema", "errors": [], "unsupported_rules": []}

            started = time.perf_counter()
            try:
                result = session.call_tool(tool, arguments)
            except McpRpcError as e:
                elapsed = (time.perf_counter() - started) * 1000.0
                meta["tool_latency_ms"] = elapsed
                return self._fail(TargetStatus.FAILED, e.code, f"JSON-RPC error from tools/call: {e}", meta, latency_ms=elapsed)
            except McpError as e:
                elapsed = (time.perf_counter() - started) * 1000.0
                meta["tool_latency_ms"] = elapsed if isinstance(e, McpTimeoutError) else None
                diag = self._drop_session()  # session state is unknown after a timeout or protocol break
                if diag:
                    meta["server_stderr_tail"] = diag
                status = TargetStatus.TIMEOUT if isinstance(e, McpTimeoutError) else TargetStatus.FAILED
                return self._fail(status, e.code, str(e), meta, latency_ms=elapsed)
            elapsed = (time.perf_counter() - started) * 1000.0

        meta["tool_latency_ms"] = elapsed
        raw_content = result.get("content")
        content: List[Any] = raw_content if isinstance(raw_content, list) else []
        texts = [c["text"] for c in content if isinstance(c, dict) and c.get("type") == "text" and isinstance(c.get("text"), str)]
        structured = result.get("structuredContent")
        meta["content_types"] = sorted({str(c.get("type")) for c in content if isinstance(c, dict)})
        meta["is_error"] = bool(result.get("isError"))
        raw_output = self._clean(result)

        if result.get("isError") is True:
            return TargetResult(
                target_id=self.target_id,
                status=TargetStatus.FAILED,
                raw_output=raw_output,
                latency_ms=elapsed,
                cost_usd=None,
                cost_basis=CostBasis.UNAVAILABLE,
                error_code="TOOL_ERROR",
                error_message=self._clean("\n".join(texts) or "tool reported isError without text content"),
                metadata=self._clean(meta),
            )

        if texts:
            output_text: Optional[str] = "\n".join(texts)
        elif structured is not None:
            output_text = json.dumps(structured, sort_keys=True)
        else:
            output_text = None
        return TargetResult(
            target_id=self.target_id,
            status=TargetStatus.SUCCESS if output_text is not None else TargetStatus.INVALID_OUTPUT,
            output_text=self._clean(output_text) if output_text is not None else None,
            raw_output=raw_output,
            latency_ms=elapsed,
            tokens_in=None,
            tokens_out=None,
            cost_usd=None,
            cost_basis=CostBasis.UNAVAILABLE,
            error_code=None if output_text is not None else "EMPTY_TOOL_RESULT",
            metadata=self._clean(meta),
        )

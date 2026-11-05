"""Deterministic offline MCP server (stdio) used only by tests/test_mcp_connector.py.

Newline-delimited JSON-RPC 2.0 on stdin/stdout, no network, no third-party imports. Tools:
    echo  -> returns its ``text`` argument
    add   -> returns structured {"sum": a + b} with no text content
    fail  -> returns a tool-level error (isError: true)
    hang  -> never answers
    leak  -> echoes the MCP_FIXTURE_SECRET env value (to prove output scrubbing)

Behaviour flags (argv):
    --bad-version   answer initialize with an unsupported protocol version
"""

import json
import os
import sys
import time

TOOLS = [
    {
        "name": "echo",
        "description": "Echo text back",
        "inputSchema": {
            "type": "object",
            "properties": {"text": {"type": "string", "minLength": 1}},
            "required": ["text"],
            "additionalProperties": False,
        },
    },
    {
        "name": "add",
        "description": "Add two numbers",
        "inputSchema": {
            "type": "object",
            "properties": {"a": {"type": "number"}, "b": {"type": "number"}},
            "required": ["a", "b"],
        },
    },
    {"name": "fail", "description": "Always fails", "inputSchema": {"type": "object", "properties": {}}},
    {"name": "hang", "description": "Never returns", "inputSchema": {"type": "object", "properties": {}}},
    {"name": "leak", "description": "Echoes an env secret", "inputSchema": {"type": "object", "properties": {}}},
]


def send(msg):
    sys.stdout.write(json.dumps(msg) + "\n")
    sys.stdout.flush()


def text(t, is_error=False):
    return {"content": [{"type": "text", "text": t}], "isError": is_error}


def main():
    bad_version = "--bad-version" in sys.argv
    ping_sent = False
    sys.stderr.write("fixture server starting\n")
    sys.stderr.flush()
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        msg = json.loads(line)
        method = msg.get("method")
        mid = msg.get("id")
        if mid is None:
            continue  # notifications (initialized, cancelled) and replies to our ping
        if method is None:
            continue
        if method == "initialize":
            version = "1999-01-01" if bad_version else msg["params"]["protocolVersion"]
            send(
                {
                    "jsonrpc": "2.0",
                    "id": mid,
                    "result": {"protocolVersion": version, "capabilities": {"tools": {}}, "serverInfo": {"name": "fixture", "version": "1.0"}},
                }
            )
        elif method == "tools/list":
            # Exercise client handling of interleaved notifications and server->client requests.
            send({"jsonrpc": "2.0", "method": "notifications/message", "params": {"level": "info", "data": "listing"}})
            if not ping_sent:
                send({"jsonrpc": "2.0", "id": "srv-1", "method": "ping"})
                ping_sent = True
            cursor = (msg.get("params") or {}).get("cursor")
            if cursor is None:
                send({"jsonrpc": "2.0", "id": mid, "result": {"tools": TOOLS[:2], "nextCursor": "page2"}})
            else:
                send({"jsonrpc": "2.0", "id": mid, "result": {"tools": TOOLS[2:]}})
        elif method == "tools/call":
            name = msg["params"]["name"]
            args = msg["params"].get("arguments") or {}
            if name == "echo":
                send({"jsonrpc": "2.0", "id": mid, "result": text(args["text"])})
            elif name == "add":
                send({"jsonrpc": "2.0", "id": mid, "result": {"content": [], "structuredContent": {"sum": args["a"] + args["b"]}}})
            elif name == "fail":
                send({"jsonrpc": "2.0", "id": mid, "result": text("fixture failure: upstream unavailable", is_error=True)})
            elif name == "hang":
                time.sleep(3600)
            elif name == "leak":
                send({"jsonrpc": "2.0", "id": mid, "result": text("secret is " + os.environ.get("MCP_FIXTURE_SECRET", ""))})
            else:
                send({"jsonrpc": "2.0", "id": mid, "error": {"code": -32602, "message": f"Unknown tool: {name}"}})
        else:
            send({"jsonrpc": "2.0", "id": mid, "error": {"code": -32601, "message": "Method not found"}})


if __name__ == "__main__":
    main()

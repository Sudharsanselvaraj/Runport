"""Unit tests for extracted Dify connector."""

import json
import urllib.request
import pytest

from runport.connectors.dify import post_chat_message, post_chat_stream, scrub_dify_secrets


class FakeHTTPResponse:
    def __init__(self, status=200, body=b"{}", headers=None, lines=None):
        self.status = status
        self._body = body
        self.headers = headers or {}
        self._lines = lines or [body]
        self._iter = iter(self._lines)

    def read(self):
        return self._body

    def __iter__(self):
        return self._iter

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass


def test_dify_blocking(monkeypatch):
    test_body = {"event": "message", "answer": "OK response", "metadata": {"usage": {"total_tokens": 42}}}
    encoded = json.dumps(test_body).encode("utf-8")

    def fake_urlopen(req, timeout=30.0):
        assert req.headers["Authorization"].startswith("Bearer app-")
        return FakeHTTPResponse(status=200, body=encoded, headers={"Content-Type": "application/json"})

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    res = post_chat_message("https://dify.example.com/v1/chat-messages", "app-SECRETKEY12345", {"query": "test"}, 10.0)

    assert res["outcome"] == "HTTP"
    assert res["http_status"] == 200
    assert json.loads(res["body_text"]) == test_body


def test_dify_streaming(monkeypatch):
    events = [
        b"data: " + json.dumps({"event": "node_started", "node_id": "1"}).encode("utf-8") + b"\n",
        b"data: " + json.dumps({"event": "message", "answer": "Hello"}).encode("utf-8") + b"\n",
        b"data: " + json.dumps({"event": "message_end", "metadata": {"usage": {"total_tokens": 10}}}).encode("utf-8") + b"\n",
    ]

    monkeypatch.setattr(urllib.request, "urlopen", lambda req, timeout=30.0: FakeHTTPResponse(status=200, lines=events))
    res = post_chat_stream("https://dify.example.com/v1/chat-messages", "app-SECRETKEY12345", {"query": "test"}, 10.0)

    assert res["outcome"] == "HTTP"
    assert res["http_status"] == 200
    assert len(res["events"]) == 3
    assert res["events"][0][1]["event"] == "node_started"
    assert res["events"][1][1]["event"] == "message"
    assert res["events"][2][1]["event"] == "message_end"


def test_scrub_dify_secrets():
    raw = "Failed with app-ABCDEF12345678 and Bearer secret-token-xyz"
    scrubbed = scrub_dify_secrets(raw)
    assert "app-ABCDEF12345678" not in scrubbed
    assert "[REDACTED_DIFY_KEY]" in scrubbed

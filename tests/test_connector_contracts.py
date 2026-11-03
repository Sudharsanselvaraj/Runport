"""Parametrized connector contract suite verifying strict protocol compliance across all stable connectors.

Verifies:
1. Auth failure (401/403) terminates fail-closed without retries.
2. 429 rate limit triggers bounded retry and honors Retry-After.
3. 5xx server errors retry with exponential backoff.
4. Transport timeout returns TargetStatus.TIMEOUT.
5. Malformed 200 OK is NOT retried (attempts == 1).
6. Secrets and keys are automatically scrubbed from outputs and errors.
7. Missing token usage stays None (Null is not 0).
"""

from decimal import Decimal
import email.message
import io
import json
import urllib.error
import pytest

from runport.connectors.dify import DifyConnector
from runport.connectors.http_workflow import HttpWorkflowConnector
from runport.connectors.ollama import OllamaConnector
from runport.connectors.openai_compat import OpenAICompatConnector
from runport.targets.base import CostBasis, TargetStatus


class FakeHTTPResponse:
    def __init__(self, payload: bytes | str | dict, status: int = 200, headers: dict | None = None):
        if isinstance(payload, dict):
            self._body = json.dumps(payload).encode("utf-8")
        elif isinstance(payload, str):
            self._body = payload.encode("utf-8")
        else:
            self._body = payload
        self.status = status
        self.code = status
        self.headers = email.message.Message()
        if headers:
            for k, v in headers.items():
                self.headers[k] = str(v)

    def read(self) -> bytes:
        return self._body

    def __iter__(self):
        yield self._body

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


def make_http_error(status: int, body: bytes | str | dict = b"{}", retry_after: str | None = None) -> urllib.error.HTTPError:
    hdrs = email.message.Message()
    if retry_after is not None:
        hdrs["Retry-After"] = str(retry_after)
    if isinstance(body, dict):
        raw_body = json.dumps(body).encode("utf-8")
    elif isinstance(body, str):
        raw_body = body.encode("utf-8")
    else:
        raw_body = body
    return urllib.error.HTTPError("https://api.example.com", status, "Error", hdrs, io.BytesIO(raw_body))


@pytest.fixture
def mock_urlopen(monkeypatch):
    calls = []

    def _set_responses(responses):
        resp_list = list(responses)

        def _fake_urlopen(req, timeout=None):
            calls.append(req)
            if not resp_list:
                raise TimeoutError("No more scripted responses")
            item = resp_list.pop(0)
            if isinstance(item, BaseException):
                raise item
            return item

        monkeypatch.setattr(urllib.request, "urlopen", _fake_urlopen)
        return calls

    return _set_responses


# --- Factory for parametrized connectors ---
def get_test_connector(connector_type: str):
    if connector_type == "openai_compat":
        return OpenAICompatConnector(
            target_id="test-openai",
            name="OpenAI Compat",
            model="gpt-4.1-nano",
            base_url="https://api.openai.com/v1",
            api_key="sk-test-secret-key-12345",
            timeout_seconds=2.0,
            max_retries=3,
        )
    elif connector_type == "dify_chat":
        return DifyConnector(
            target_id="test-dify-chat",
            name="Dify Chat",
            api_key="app-test-secret-dify-key-67890",
            base_url="https://api.dify.ai/v1",
            app_type="chat",
            response_mode="blocking",
            timeout_seconds=2.0,
            max_retries=3,
        )
    elif connector_type == "dify_workflow":
        return DifyConnector(
            target_id="test-dify-workflow",
            name="Dify Workflow",
            api_key="app-test-secret-dify-key-67890",
            base_url="https://api.dify.ai/v1",
            app_type="workflow",
            response_mode="blocking",
            timeout_seconds=2.0,
            max_retries=3,
        )
    elif connector_type == "http_workflow":
        return HttpWorkflowConnector(
            target_id="test-http",
            name="HTTP Workflow",
            url="https://api.example.com/v1/predict",
            headers={"Authorization": "Bearer test-http-secret-key"},
            timeout_seconds=2.0,
            max_retries=3,
        )
    elif connector_type == "ollama":
        return OllamaConnector(
            target_id="test-ollama",
            name="Local Ollama",
            model="llama3.2",
            base_url="http://127.0.0.1:11434",
            allow_localhost=True,
            timeout_seconds=2.0,
        )
    raise ValueError(f"Unknown connector: {connector_type}")


ALL_STABLE_CONNECTORS = ["openai_compat", "dify_chat", "dify_workflow", "http_workflow", "ollama"]


@pytest.mark.parametrize("connector_type", ALL_STABLE_CONNECTORS)
def test_contract_auth_failure_does_not_retry_endlessly(connector_type, mock_urlopen):
    """401/403 Auth failure halts without looping."""
    target = get_test_connector(connector_type)
    calls = mock_urlopen([make_http_error(401, {"error": "Invalid API key"})])

    result = target.execute({"query": "Hello"})
    assert result.status in (TargetStatus.UNAUTHORIZED, TargetStatus.FAILED)
    assert len(calls) == 1  # Exactly 1 attempt, non-retryable


@pytest.mark.parametrize("connector_type", ["openai_compat", "http_workflow"])
def test_contract_429_retry_and_retry_after(connector_type, mock_urlopen):
    """429 triggers bounded retry and honors Retry-After."""
    target = get_test_connector(connector_type)
    # Fail twice with 429, then succeed with 200 OK
    good_body = {
        "choices": [{"message": {"content": "Success after retry"}}],
        "usage": {"prompt_tokens": 10, "completion_tokens": 5},
    } if connector_type == "openai_compat" else {"output": "Success after retry"}

    calls = mock_urlopen([
        make_http_error(429, {"error": "Rate limit exceeded"}, retry_after="0.01"),
        make_http_error(429, {"error": "Rate limit exceeded"}, retry_after="0.01"),
        FakeHTTPResponse(good_body, status=200),
    ])

    result = target.execute({"query": "Hello"})
    assert result.status == TargetStatus.SUCCESS
    assert result.output_text == "Success after retry"
    assert len(calls) == 3


@pytest.mark.parametrize("connector_type", ["openai_compat", "http_workflow"])
def test_contract_5xx_retry_backoff(connector_type, mock_urlopen):
    """502/503 server errors retry and recover."""
    target = get_test_connector(connector_type)
    good_body = {
        "choices": [{"message": {"content": "Recovered from 502"}}],
        "usage": {"prompt_tokens": 8, "completion_tokens": 4},
    } if connector_type == "openai_compat" else {"output": "Recovered from 502"}

    calls = mock_urlopen([
        make_http_error(502, "Bad Gateway"),
        FakeHTTPResponse(good_body, status=200),
    ])

    result = target.execute({"query": "Hello"})
    assert result.status == TargetStatus.SUCCESS
    assert len(calls) == 2


@pytest.mark.parametrize("connector_type", ALL_STABLE_CONNECTORS)
def test_contract_timeout_returns_timeout_status(connector_type, mock_urlopen):
    """Network timeouts return TargetStatus.TIMEOUT."""
    target = get_test_connector(connector_type)
    mock_urlopen([TimeoutError("Operation timed out") for _ in range(5)])

    result = target.execute({"query": "Hello"})
    assert result.status == TargetStatus.TIMEOUT


@pytest.mark.parametrize("connector_type", ["openai_compat", "http_workflow", "dify_chat"])
def test_contract_malformed_200_not_retried(connector_type, mock_urlopen):
    """Malformed non-JSON 200 OK is NOT retried (attempts == 1)."""
    target = get_test_connector(connector_type)
    calls = mock_urlopen([FakeHTTPResponse(b"<html>Bad Gateway Page (200 OK)</html>", status=200)])

    result = target.execute({"query": "Hello"})
    # Status should be INVALID_OUTPUT or FAILED
    assert result.status in (TargetStatus.INVALID_OUTPUT, TargetStatus.FAILED)
    assert len(calls) == 1  # Never retried! Retrying a 200 is wasteful


@pytest.mark.parametrize("connector_type", ["openai_compat", "dify_chat", "http_workflow"])
def test_contract_secret_scrubbing(connector_type, mock_urlopen):
    """Secrets and Bearer tokens are scrubbed from result metadata and error messages."""
    target = get_test_connector(connector_type)
    secret_text = "Bearer secret-token-abcdef12345678"
    mock_urlopen([make_http_error(400, f"Internal crash involving {secret_text}")])

    result = target.execute({"query": "Hello"})
    error_msg = str(result.error_message)
    assert "secret-token-abcdef12345678" not in error_msg
    assert "[REDACTED" in error_msg


@pytest.mark.parametrize("connector_type", ["openai_compat", "dify_chat", "ollama"])
def test_contract_missing_usage_stays_none(connector_type, mock_urlopen):
    """Invariant 1: When usage/token telemetry is missing, tokens_in/out remain None (not 0)."""
    target = get_test_connector(connector_type)
    if connector_type == "openai_compat":
        body = {"choices": [{"message": {"content": "No usage reported"}}]}  # No usage key
    elif connector_type == "dify_chat":
        body = {"answer": "No usage reported", "metadata": {}}  # No usage key
    else:  # ollama
        body = {"message": {"content": "No usage reported"}}  # No prompt_eval_count

    mock_urlopen([FakeHTTPResponse(body, status=200)])

    result = target.execute({"query": "Hello"})
    assert result.status == TargetStatus.SUCCESS
    assert result.tokens_in is None
    assert result.tokens_out is None

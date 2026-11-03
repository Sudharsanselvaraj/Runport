"""Unit tests for generic Runport workflow and model connectors."""

import io
import json
import urllib.error
import pytest
from decimal import Decimal

from runport.connectors import (
    FlowiseConnector,
    HttpWorkflowConnector,
    LangGraphConnector,
    LangflowConnector,
    N8nConnector,
    OpenAICompatConnector,
    PythonCallableTarget,
    SubprocessTarget,
)
from runport.targets import TargetPricing, TargetStatus, TargetType


class FakeHttpResponse:
    def __init__(self, body_bytes: bytes, status: int = 200, headers: dict = None):
        self._body = body_bytes
        self.status = status
        self.headers = headers or {}

    def read(self, *args):
        return self._body

    def getcode(self):
        return self.status

    def info(self):
        return self.headers

    def close(self):
        pass

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


def test_http_workflow_connector_success(monkeypatch):
    """HttpWorkflowConnector properly sends payload, extracts path, and records metrics."""
    response_payload = {
        "data": {
            "response": {
                "text": "Hello world from workflow",
            }
        },
        "usage": {"input_tokens": 15, "output_tokens": 8},
    }

    def fake_urlopen(req, timeout=None):
        return FakeHttpResponse(json.dumps(response_payload).encode("utf-8"))

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

    pricing = TargetPricing(
        input_usd_per_1m=Decimal("1.00"),
        output_usd_per_1m=Decimal("2.00"),
    )
    connector = HttpWorkflowConnector(
        target_id="custom-http",
        name="Custom HTTP Agent",
        url="https://api.example.com/workflow",
        payload_template={"user_query": "{{query}}", "mode": "eval"},
        output_path="data.response.text",
        pricing=pricing,
    )

    result = connector.execute({"query": "What is 2+2?"})

    assert result.is_success is True
    assert result.output_text == "Hello world from workflow"
    assert result.tokens_in == 15
    assert result.tokens_out == 8
    assert result.cost_usd is not None
    assert result.cost_usd > Decimal("0")
    assert result.latency_ms is not None and result.latency_ms >= 0


def test_http_workflow_connector_rate_limit(monkeypatch):
    """HttpWorkflowConnector handles 429 rate limit errors."""
    def fake_urlopen(req, timeout=None):
        raise urllib.error.HTTPError(
            url="https://api.example.com/workflow",
            code=429,
            msg="Too Many Requests",
            hdrs={},
            fp=io.BytesIO(b'{"error": "rate limit exceeded"}'),
        )

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

    connector = HttpWorkflowConnector(
        target_id="custom-http",
        name="Custom HTTP Agent",
        url="https://api.example.com/workflow",
    )
    result = connector.execute({"query": "test"})

    assert result.status == TargetStatus.RATE_LIMITED
    assert result.error_code == "429"


def test_http_workflow_connector_secret_scrubbing(monkeypatch):
    """HttpWorkflowConnector scrubs secret keys in HTTP error messages."""
    def fake_urlopen(req, timeout=None):
        raise urllib.error.HTTPError(
            url="https://api.example.com/workflow",
            code=400,
            msg="Bad Request",
            hdrs={},
            fp=io.BytesIO(b'{"error": "invalid token sk-dummy-mock-secret-key-1234567890"}'),
        )

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

    connector = HttpWorkflowConnector(
        target_id="custom-http",
        name="Custom HTTP Agent",
        url="https://api.example.com/workflow",
    )
    result = connector.execute({"query": "test"})

    assert result.status == TargetStatus.FAILED
    assert result.error_code == "400"
    assert "sk-dummy-mock-secret-key-1234567890" not in str(result.error_message)
    assert "[REDACTED_API_KEY]" in str(result.error_message)


def test_openai_compat_connector(monkeypatch):
    """OpenAICompatConnector constructs standard messages and extracts choices."""
    openai_response = {
        "model": "gpt-4.1-mini",
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": "4"},
                "finish_reason": "stop",
            }
        ],
        "usage": {"prompt_tokens": 10, "completion_tokens": 1},
    }

    recorded_requests = []

    def fake_urlopen(req, timeout=None):
        recorded_requests.append(req)
        return FakeHttpResponse(json.dumps(openai_response).encode("utf-8"))

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

    target = OpenAICompatConnector(
        target_id="test-openai",
        name="Test OpenAI",
        model="gpt-4.1-mini",
        api_key="sk-test-key",
        pricing=TargetPricing(input_usd_per_1m=Decimal("0.15"), output_usd_per_1m=Decimal("0.60")),
    )

    res = target.execute({"query": "What is 2+2?", "system_prompt": "You are a math tutor."})

    assert res.is_success is True
    assert res.output_text == "4"
    assert res.tokens_in == 10
    assert res.tokens_out == 1
    assert len(recorded_requests) == 1
    req = recorded_requests[0]
    assert req.headers.get("Authorization") == "Bearer sk-test-key"
    body = json.loads(req.data.decode("utf-8"))
    assert body["model"] == "gpt-4.1-mini"
    assert len(body["messages"]) == 2


def test_flowise_connector_config():
    """FlowiseConnector builds expected prediction endpoint URL and headers."""
    connector = FlowiseConnector(
        target_id="flowise-1",
        name="Flowise Support",
        base_url="https://flowise.example.com",
        chatflow_id="cf-12345",
        api_key="flowise-token-abc",
        override_config={"sessionId": "session-1"},
    )
    assert connector.url == "https://flowise.example.com/api/v1/prediction/cf-12345"
    assert connector.headers.get("Authorization") == "Bearer flowise-token-abc"
    assert connector.target_type == TargetType.WORKFLOW_FLOWISE


def test_langflow_connector_config():
    """LangflowConnector builds expected flow run endpoint URL and headers."""
    connector = LangflowConnector(
        target_id="langflow-1",
        name="Langflow Agent",
        base_url="https://langflow.example.com",
        flow_id="flow-999",
        api_key="lf-token-xyz",
        tweaks={"temperature": 0.2},
    )
    assert connector.url == "https://langflow.example.com/api/v1/run/flow-999"
    assert connector.headers.get("x-api-key") == "lf-token-xyz"
    assert connector.target_type == TargetType.WORKFLOW_LANGFLOW


def test_n8n_connector_config():
    """N8nConnector sets webhook URL and custom auth headers."""
    connector = N8nConnector(
        target_id="n8n-1",
        name="n8n Pipeline",
        webhook_url="https://n8n.example.com/webhook/test-uuid",
        auth_header={"X-N8N-Key": "secret"},
    )
    assert connector.url == "https://n8n.example.com/webhook/test-uuid"
    assert connector.headers.get("X-N8N-Key") == "secret"
    assert connector.target_type == TargetType.WORKFLOW_N8N


def test_langgraph_connector_config():
    """LangGraphConnector sets assistant ID and endpoint."""
    connector = LangGraphConnector(
        target_id="langgraph-1",
        name="LangGraph Chat",
        base_url="https://langgraph.example.com",
        assistant_id="asst-agent-01",
        api_key="lg-token",
    )
    assert connector.url == "https://langgraph.example.com/runs/wait"
    assert connector.headers.get("x-api-key") == "lg-token"
    assert connector.target_type == TargetType.WORKFLOW_LANGGRAPH


def test_python_callable_target():
    """PythonCallableTarget invokes in-memory Python callable and returns result."""
    def my_agent(inputs):
        return f"Echo: {inputs.get('query')}"

    target = PythonCallableTarget(
        target_id="py-callable",
        name="Python Agent",
        func=my_agent,
    )
    result = target.execute({"query": "Hello Antigravity"})
    assert result.is_success is True
    assert result.output_text == "Echo: Hello Antigravity"
    assert result.target_id == "py-callable"


def test_subprocess_target():
    """SubprocessTarget runs CLI process and returns stdout."""
    target = SubprocessTarget(
        target_id="subproc-echo",
        name="Subprocess Echo",
        command=["python3", "-c", "import sys, json; data=json.load(sys.stdin); print(f'Result: {data[\"query\"]}')"],
    )
    result = target.execute({"query": "Hello CLI"})
    assert result.is_success is True
    assert result.output_text == "Result: Hello CLI"

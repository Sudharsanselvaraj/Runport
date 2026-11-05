"""Builds Targets from declarative specs, and the single source of truth for connector capabilities.

Specs come from the workspace file (``targets:`` in runport.yaml) or from an API/SDK caller. Secret values never
live in a spec: a value written as ``$NAME`` or containing ``${NAME}`` is read from the environment when the target
is built. ``spec_digest`` hashes the spec as written (with the ``$NAME`` references, not the values), so plan
fingerprints can bind a target's definition without ever containing a credential.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Dict, FrozenSet, List, Mapping, Optional

from runport.targets.base import BillingMode, Target, TargetPricing

_ENV_REF = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}")
_SENSITIVE_HEADER = re.compile(r"auth|key|token|secret|cookie", re.IGNORECASE)


class TargetSpecError(ValueError):
    """A target spec is invalid, references a missing environment variable, or embeds a literal secret."""


def _resolve(value: Any, path: str) -> Any:
    if isinstance(value, str):
        if value.startswith("$") and not value.startswith("${") and re.fullmatch(r"\$[A-Za-z_][A-Za-z0-9_]*", value):
            name = value[1:]
            if name not in os.environ:
                raise TargetSpecError(f"{path}: environment variable '{name}' is not set")
            return os.environ[name]

        def sub(m: "re.Match[str]") -> str:
            if m.group(1) not in os.environ:
                raise TargetSpecError(f"{path}: environment variable '{m.group(1)}' is not set")
            return os.environ[m.group(1)]

        return _ENV_REF.sub(sub, value)
    if isinstance(value, dict):
        return {k: _resolve(v, f"{path}.{k}") for k, v in value.items()}
    if isinstance(value, list):
        return [_resolve(v, f"{path}[{i}]") for i, v in enumerate(value)]
    return value


def _is_env_ref(value: Any) -> bool:
    return isinstance(value, str) and (bool(re.fullmatch(r"\$[A-Za-z_][A-Za-z0-9_]*", value)) or bool(_ENV_REF.search(value)))


def check_spec_has_no_literal_secrets(name: str, spec: Mapping[str, Any]) -> None:
    """Credentials in a declarative spec must be environment references, never literal values."""
    if spec.get("api_key") is not None and not _is_env_ref(spec["api_key"]):
        raise TargetSpecError(f"target '{name}': api_key must be an environment reference such as $OPENAI_API_KEY")
    for header, value in (spec.get("headers") or {}).items():
        if _SENSITIVE_HEADER.search(str(header)) and not _is_env_ref(value):
            raise TargetSpecError(f"target '{name}': header '{header}' must use an environment reference such as 'Bearer ${{TOKEN}}'")


def spec_digest(spec: Mapping[str, Any]) -> str:
    return hashlib.sha256(json.dumps(spec, sort_keys=True, default=str).encode("utf-8")).hexdigest()


def _pricing(spec: Mapping[str, Any]) -> Optional[TargetPricing]:
    p = spec.get("pricing")
    if not p:
        return None
    dec = lambda k: Decimal(str(p[k])) if p.get(k) is not None else None  # noqa: E731
    return TargetPricing(
        input_usd_per_1m=dec("input_usd_per_1m"), output_usd_per_1m=dec("output_usd_per_1m"), fixed_usd_per_request=dec("fixed_usd_per_request")
    )


def _billing(spec: Mapping[str, Any]) -> Optional[BillingMode]:
    return BillingMode(spec["billing"]) if spec.get("billing") else None


def build_target(name: str, spec: Mapping[str, Any], *, allow_local_processes: bool = True) -> Target:
    """Constructs a Target. ``allow_local_processes=False`` refuses specs that launch code (python, subprocess, mcp stdio)."""
    kind = str(spec.get("type") or "").lower()
    if kind not in CONNECTORS:
        raise TargetSpecError(f"target '{name}': unknown type '{kind}'. Known: {', '.join(sorted(CONNECTORS))}")
    if kind in _PROCESS_KINDS or (kind == "mcp" and spec.get("command")):
        if not allow_local_processes:
            raise TargetSpecError(f"target '{name}': type '{kind}' runs local code and is not allowed from this interface")
    s: Dict[str, Any] = _resolve(dict(spec), name)
    net: Dict[str, Any] = {k: s[k] for k in ("allow_localhost", "allow_private", "host_allowlist") if k in s}
    common: Dict[str, Any] = {"target_id": name, "name": s.get("name", name)}
    timeout: Dict[str, Any] = {"timeout_seconds": float(s["timeout_seconds"])} if "timeout_seconds" in s else {}

    if kind == "openrouter":
        from runport.connectors.openrouter import OpenRouterTarget

        return OpenRouterTarget(model_id=s.get("model") or name, target_id=name, **timeout)
    if kind == "openai_compat":
        from runport.connectors.openai_compat import OpenAICompatConnector

        oc_kwargs: Dict[str, Any] = {"allow_localhost": s.get("allow_localhost", False), "allow_private": s.get("allow_private", False)}
        if "host_allowlist" in s:
            oc_kwargs["host_allowlist"] = s["host_allowlist"]
        return OpenAICompatConnector(
            **common,
            model=s["model"],
            base_url=s.get("base_url", "https://api.openai.com/v1"),
            api_key=s.get("api_key"),
            custom_headers=s.get("headers"),
            pricing=_pricing(s),
            billing=_billing(s),
            **oc_kwargs,
            **timeout,
        )
    if kind == "http_workflow":
        from runport.connectors.http_workflow import HttpWorkflowConnector

        return HttpWorkflowConnector(
            **common,
            url=s["url"],
            method=s.get("method", "POST"),
            headers=s.get("headers"),
            payload_template=s.get("payload_template"),
            output_path=s.get("output_path"),
            pricing=_pricing(s),
            billing=_billing(s),
            **net,
            **timeout,
        )
    if kind == "ollama":
        from runport.connectors.ollama import OllamaConnector

        return OllamaConnector(**common, model=s["model"], base_url=s.get("base_url", "http://127.0.0.1:11434"), billing=_billing(s), **timeout)
    if kind == "dify":
        from runport.connectors.dify import DifyConnector

        return DifyConnector(
            **common,
            api_key=s["api_key"],
            base_url=s.get("base_url", "https://api.dify.ai/v1"),
            app_type=s.get("app_type", "chat"),
            pricing=_pricing(s),
            billing=_billing(s),
            **{k: v for k, v in net.items() if k != "allow_private"},
            **timeout,
        )
    if kind in ("flowise", "langflow", "n8n", "langgraph"):
        from runport.connectors.flowise import FlowiseConnector
        from runport.connectors.langflow import LangflowConnector
        from runport.connectors.langgraph import LangGraphConnector
        from runport.connectors.n8n import N8nConnector

        if kind == "flowise":
            t: Target = FlowiseConnector(**common, base_url=s["base_url"], chatflow_id=s["flow_id"], api_key=s.get("api_key"), pricing=_pricing(s))
        elif kind == "langflow":
            t = LangflowConnector(**common, base_url=s["base_url"], flow_id=s["flow_id"], api_key=s.get("api_key"), pricing=_pricing(s))
        elif kind == "n8n":
            t = N8nConnector(**common, webhook_url=s["url"], auth_header=s.get("headers"), pricing=_pricing(s))
        else:
            t = LangGraphConnector(**common, base_url=s["base_url"], assistant_id=s.get("assistant_id", "agent"), api_key=s.get("api_key"), pricing=_pricing(s))
        if s.get("billing"):
            t.billing = BillingMode(s["billing"])
        return t
    if kind == "python":
        from runport.connectors.python_target import PythonCallableTarget

        return PythonCallableTarget(**common, func=s["callable"], **timeout)
    if kind == "subprocess":
        from runport.connectors.python_target import SubprocessTarget

        return SubprocessTarget(**common, command=list(s["command"]), **timeout)
    if kind == "mcp":
        from runport.connectors.mcp import McpToolTarget

        return McpToolTarget(
            **common,
            command=s.get("command"),
            url=s.get("url"),
            headers=s.get("headers"),
            tool_name=s.get("tool"),
            arguments_template=s.get("arguments_template"),
            billing=_billing(s),
            **net,
            **timeout,
        )
    raise TargetSpecError(f"target '{name}': type '{kind}' has no builder")  # pragma: no cover


_PROCESS_KINDS = frozenset({"python", "subprocess"})


# --------------------------------------------------------------------------------------------------
# Capability registry: the only place connector status and capabilities are declared.
# Every "yes" here must be backed by code in the module and by a test (see tests/test_capability_registry.py).
# --------------------------------------------------------------------------------------------------

YES, NO, PARTIAL = "yes", "no", "partial"


@dataclass(frozen=True)
class ConnectorInfo:
    id: str
    name: str
    module: Optional[str]  # relative to src/runport/; None = no dedicated module
    status: str  # stable | experimental | via | planned
    integration: str  # native | generic_http | openai_compatible | in_process | trace_import | none
    tested: str
    streaming: str
    tool_calls: str
    structured_output: str
    per_step_trace: str
    usage_reporting: str
    cost_reporting: str
    error_timeout_handling: str
    via: Optional[str] = None
    notes: str = ""


def _c(id: str, name: str, module: Optional[str], status: str, integration: str, *caps: str, via: Optional[str] = None, notes: str = "") -> ConnectorInfo:
    tested, streaming, tool_calls, structured, per_step, tokens, cost, errors = caps
    return ConnectorInfo(
        id=id,
        name=name,
        module=module,
        status=status,
        integration=integration,
        tested=tested,
        streaming=streaming,
        tool_calls=tool_calls,
        structured_output=structured,
        per_step_trace=per_step,
        usage_reporting=tokens,
        cost_reporting=cost,
        error_timeout_handling=errors,
        via=via,
        notes=notes,
    )


#            tested streaming tools structured per_step tokens cost errors
CONNECTOR_MATRIX: List[ConnectorInfo] = [
    _c(
        "openai_compat",
        "OpenAI / OpenAI-compatible",
        "connectors/openai_compat.py",
        "stable",
        "native",
        YES,
        NO,
        NO,
        PARTIAL,
        NO,
        YES,
        PARTIAL,
        YES,
        notes="Chat Completions only; response_format is passed through, not validated. Cost only with configured pricing (ESTIMATED); otherwise UNRESOLVED for remote hosts.",
    ),
    _c(
        "openrouter",
        "OpenRouter",
        "connectors/openrouter.py",
        "stable",
        "native",
        YES,
        NO,
        NO,
        NO,
        NO,
        YES,
        YES,
        YES,
        notes="ACTUAL when OpenRouter reports USD cost, ESTIMATED from catalog x reported tokens, otherwise UNRESOLVED.",
    ),
    _c(
        "dify",
        "Dify",
        "connectors/dify.py",
        "stable",
        "native",
        YES,
        YES,
        NO,
        NO,
        PARTIAL,
        YES,
        PARTIAL,
        YES,
        notes="Streaming via SSE. Workflow apps record node steps in metadata (not yet as trajectory spans).",
    ),
    _c(
        "http_workflow",
        "Generic HTTP endpoint",
        "connectors/http_workflow.py",
        "stable",
        "generic_http",
        YES,
        NO,
        NO,
        NO,
        NO,
        PARTIAL,
        PARTIAL,
        YES,
        notes="Tokens only if the response has a usage object. Cost only with configured pricing.",
    ),
    _c(
        "python_target",
        "Python callable",
        "connectors/python_target.py",
        "stable",
        "in_process",
        YES,
        NO,
        NO,
        PARTIAL,
        NO,
        NO,
        NO,
        YES,
        notes="Local execution: cost UNAVAILABLE. Returns dicts as JSON text.",
    ),
    _c(
        "subprocess",
        "Subprocess (stdin/stdout)",
        "connectors/python_target.py",
        "stable",
        "in_process",
        YES,
        NO,
        NO,
        NO,
        NO,
        NO,
        NO,
        YES,
        notes="Local execution: cost UNAVAILABLE.",
    ),
    _c(
        "ollama",
        "Ollama",
        "connectors/ollama.py",
        "stable",
        "native",
        YES,
        NO,
        NO,
        PARTIAL,
        NO,
        YES,
        NO,
        YES,
        notes="Non-streaming /api/chat. format=json supported. Local hosts book UNAVAILABLE; remote hosts are billable.",
    ),
    _c(
        "mcp",
        "MCP server (tools)",
        "connectors/mcp.py",
        "experimental",
        "native",
        YES,
        NO,
        YES,
        YES,
        NO,
        NO,
        NO,
        YES,
        notes="Calls MCP tools directly (stdio, Streamable HTTP); validates arguments against inputSchema; returns structuredContent.",
    ),
    _c(
        "flowise",
        "Flowise",
        "connectors/flowise.py",
        "experimental",
        "generic_http",
        PARTIAL,
        NO,
        NO,
        NO,
        NO,
        NO,
        NO,
        YES,
        notes="Thin HTTP wrapper over the prediction endpoint; no streaming.",
    ),
    _c(
        "langflow",
        "Langflow",
        "connectors/langflow.py",
        "experimental",
        "generic_http",
        PARTIAL,
        NO,
        NO,
        NO,
        NO,
        NO,
        NO,
        YES,
        notes="Thin HTTP wrapper over the run endpoint; no streaming.",
    ),
    _c("n8n", "n8n", "connectors/n8n.py", "experimental", "generic_http", PARTIAL, NO, NO, NO, NO, NO, NO, YES, notes="Webhook POST."),
    _c(
        "langgraph",
        "LangGraph",
        "connectors/langgraph.py",
        "experimental",
        "generic_http",
        PARTIAL,
        NO,
        NO,
        NO,
        NO,
        NO,
        NO,
        YES,
        notes="POST /runs/wait and read the last message. No streaming and no per-step trace yet.",
    ),
    # Reached through another connector: inherit that connector's capabilities, never shown as native.
    _c("vllm", "vLLM", None, "via", "openai_compatible", NO, NO, NO, NO, NO, YES, PARTIAL, YES, via="openai_compat"),
    _c("lm_studio", "LM Studio", None, "via", "openai_compatible", NO, NO, NO, NO, NO, YES, PARTIAL, YES, via="openai_compat"),
    _c("localai", "LocalAI", None, "via", "openai_compatible", NO, NO, NO, NO, NO, YES, PARTIAL, YES, via="openai_compat"),
    _c("litellm", "LiteLLM proxy", None, "via", "openai_compatible", NO, NO, NO, NO, NO, YES, PARTIAL, YES, via="openai_compat"),
    _c("groq", "Groq", None, "via", "openai_compatible", NO, NO, NO, NO, NO, YES, PARTIAL, YES, via="openai_compat"),
    _c("together", "Together", None, "via", "openai_compatible", NO, NO, NO, NO, NO, YES, PARTIAL, YES, via="openai_compat"),
    _c("fireworks", "Fireworks", None, "via", "openai_compatible", NO, NO, NO, NO, NO, YES, PARTIAL, YES, via="openai_compat"),
    _c("deepinfra", "DeepInfra", None, "via", "openai_compatible", NO, NO, NO, NO, NO, YES, PARTIAL, YES, via="openai_compat"),
    _c("deepseek", "DeepSeek", None, "via", "openai_compatible", NO, NO, NO, NO, NO, YES, PARTIAL, YES, via="openai_compat"),
    _c("mistral", "Mistral", None, "via", "openai_compatible", NO, NO, NO, NO, NO, YES, PARTIAL, YES, via="openai_compat"),
    _c(
        "anthropic",
        "Anthropic",
        None,
        "via",
        "openai_compatible",
        NO,
        NO,
        NO,
        NO,
        NO,
        YES,
        YES,
        YES,
        via="openrouter",
        notes="No native Messages API adapter; reach Claude models through OpenRouter.",
    ),
    _c(
        "gemini",
        "Gemini",
        None,
        "via",
        "openai_compatible",
        NO,
        NO,
        NO,
        NO,
        NO,
        YES,
        YES,
        YES,
        via="openrouter",
        notes="No native Gemini adapter; reach Gemini models through OpenRouter.",
    ),
    _c(
        "langchain",
        "LangChain",
        None,
        "planned",
        "none",
        NO,
        NO,
        NO,
        NO,
        NO,
        NO,
        NO,
        NO,
        notes="No callback integration. Benchmark a LangChain app today via http_workflow or a python callable.",
    ),
    _c("crewai", "CrewAI", None, "planned", "none", NO, NO, NO, NO, NO, NO, NO, NO, notes="Use http_workflow or a python callable."),
    _c("llamaindex", "LlamaIndex", None, "planned", "none", NO, NO, NO, NO, NO, NO, NO, NO, notes="Use http_workflow or a python callable."),
]

CONNECTORS: Dict[str, str] = {
    # spec "type" -> connector id in the matrix
    "openrouter": "openrouter",
    "openai_compat": "openai_compat",
    "http_workflow": "http_workflow",
    "ollama": "ollama",
    "dify": "dify",
    "flowise": "flowise",
    "langflow": "langflow",
    "n8n": "n8n",
    "langgraph": "langgraph",
    "python": "python_target",
    "subprocess": "subprocess",
    "mcp": "mcp",
}

NATIVE_STATUSES: FrozenSet[str] = frozenset({"stable", "experimental"})


def connector_info(connector_id: str) -> ConnectorInfo:
    for c in CONNECTOR_MATRIX:
        if c.id == connector_id:
            return c
    raise KeyError(connector_id)


_STATUS_LABEL = {"stable": "**Stable**", "experimental": "*Experimental*", "via": "Via", "planned": "Planned"}
_CELL = {YES: "yes", NO: "—", PARTIAL: "partial"}


def render_matrix_markdown() -> str:
    """The connector capability table, generated from CONNECTOR_MATRIX (docs embed it between markers)."""
    head = (
        "| Connector | Name | Status | Integration | Tested | Streaming | Tool calls | Structured output | Per-step trace | Usage | Cost | Errors / timeouts |"
    )
    rows = [head, "|:---|:---|:---:|:---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|"]
    for c in CONNECTOR_MATRIX:
        integration = f"via `{c.via}`" if c.via else c.integration.replace("_", " ")
        caps = [c.tested, c.streaming, c.tool_calls, c.structured_output, c.per_step_trace, c.usage_reporting, c.cost_reporting, c.error_timeout_handling]
        rows.append(f"| `{c.id}` | {c.name} | {_STATUS_LABEL[c.status]} | {integration} | " + " | ".join(_CELL[v] for v in caps) + " |")
    return "\n".join(rows)


MATRIX_BEGIN = "<!-- BEGIN CONNECTOR MATRIX (generated from src/runport/connectors/registry.py; do not edit by hand) -->"
MATRIX_END = "<!-- END CONNECTOR MATRIX -->"

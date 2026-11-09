"""Runport MCP server over stdio (newline-delimited JSON-RPC 2.0). No third-party dependency.

What an agent can do: discover connectors, models, workspace targets and datasets; validate a target; create a
benchmark plan; ask a person to approve it; execute a plan a person has approved; read runs and results.

What an agent cannot do, by construction:
* approve spend. There is no approve tool, and the approval store rejects every channel this server could use.
  A person approves with `runport approve <plan_id>` or in the Web UI.
* run anything outside ExecutionService / GenericRunner. Execution re-derives the plan fingerprint and consumes
  the approval atomically, so a plan runs once and only as approved.
* point Runport at arbitrary URLs or commands. Targets are the ones declared in runport.yaml or catalog models.
* read secrets. Target listings carry header names only, and every result is scrubbed.
"""

from __future__ import annotations

import json
import sys
from typing import IO, Any, Callable, Dict, List, Optional, Tuple

from runport import __version__
from runport.connectors.mcp import SUPPORTED_PROTOCOL_VERSIONS, validate_json_schema
from runport.providers.base import scrub_secrets

SERVER_INFO = {"name": "runport", "version": __version__}
DEFAULT_PROTOCOL_VERSION = "2026-07-28"

_STR = {"type": "string"}


class ToolError(Exception):
    """Reported to the client as a tool result with isError: true."""


def _schema(props: Dict[str, Any], required: Optional[List[str]] = None) -> Dict[str, Any]:
    return {"type": "object", "properties": props, "required": required or [], "additionalProperties": False}


class RunportMcpServer:
    def __init__(self, service_factory: Optional[Callable[[], Any]] = None) -> None:
        from runport.services.execution import ExecutionService

        self._service_factory = service_factory or ExecutionService
        self.protocol_version: Optional[str] = None
        self.tools: Dict[str, Tuple[str, Dict[str, Any], Callable[[Dict[str, Any]], Any]]] = {
            "list_connectors": ("Connector capability matrix: what each connector implements and how it is tested.", _schema({}), self._list_connectors),
            "list_models": ("Catalog models with verified pricing that can be benchmarked through OpenRouter.", _schema({}), self._list_models),
            "list_targets": ("Targets declared in runport.yaml (type, billing mode, header names only).", _schema({}), self._list_targets),
            "list_datasets": ("Evaluation datasets in data/evaluation with case counts.", _schema({}), self._list_datasets),
            "validate_target": (
                "Builds a declared target or catalog model without sending anything and reports its type, billing and pricing.",
                _schema({"target_id": _STR}, ["target_id"]),
                self._validate_target,
            ),
            "create_benchmark_plan": (
                "Creates a fingerprinted plan with worst-case spend and blockers. Sends nothing. A person must approve it.",
                _schema(
                    {
                        "target_ids": {"type": "array", "items": _STR, "minItems": 1},
                        "dataset_name": _STR,
                        "sample_size": {"type": "integer", "minimum": 1},
                    },
                    ["target_ids", "dataset_name"],
                ),
                self._create_plan,
            ),
            "request_benchmark_approval": (
                "Returns how a person approves this plan (CLI or Web UI) and its current status. It does not approve anything.",
                _schema({"plan_id": _STR}, ["plan_id"]),
                self._request_approval,
            ),
            "get_plan_status": ("Status of a plan: PENDING, APPROVED (by whom) or CONSUMED.", _schema({"plan_id": _STR}, ["plan_id"]), self._plan_status),
            "execute_approved_benchmark": (
                "Executes a plan that a person has approved, once, through the guarded runner. Refused otherwise.",
                _schema({"plan_id": _STR}, ["plan_id"]),
                self._execute,
            ),
            "get_run": ("Run summary by run id.", _schema({"run_id": _STR}, ["run_id"]), self._get_run),
            "get_evaluation_results": (
                "Per-case results of a run (optionally only failures).",
                _schema({"run_id": _STR, "only_failures": {"type": "boolean"}, "limit": {"type": "integer", "minimum": 1, "maximum": 500}}, ["run_id"]),
                self._get_results,
            ),
            "compare_runs": ("Side-by-side metrics of two runs.", _schema({"run_a": _STR, "run_b": _STR}, ["run_a", "run_b"]), self._compare),
            "get_budget_status": (
                "Current spend against ceilings, remaining limits, and unresolved spend count.",
                _schema({}),
                lambda args: self._budget(),
            ),
            "list_jobs": (
                "List recent asynchronous benchmark execution jobs.",
                _schema({"limit": {"type": "integer", "minimum": 1, "maximum": 500}}),
                self._list_jobs,
            ),
            "cancel_job": (
                "Cooperatively cancel a running or queued job by job_id.",
                _schema({"job_id": _STR}, ["job_id"]),
                self._cancel_job,
            ),
        }
        self._assert_no_approval_tools()

    def _assert_no_approval_tools(self) -> None:
        for name in self.tools:
            if "approve_plan" in name.lower() or name.lower().startswith("approve"):
                raise RuntimeError(f"Self-approval tool '{name}' is strictly forbidden by Runport security policy.")

    def register_tool(self, name: str, description: str, schema: Dict[str, Any], fn: Callable[[Dict[str, Any]], Any]) -> None:
        if "approve_plan" in name.lower() or name.lower().startswith("approve"):
            raise ValueError(f"Self-approval tool '{name}' is strictly forbidden by Runport security policy.")
        self.tools[name] = (description, schema, fn)

    # ------------------------------------------------------------------ protocol

    def handle(self, msg: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        if not isinstance(msg, dict) or msg.get("jsonrpc") != "2.0" or "method" not in msg:
            return None if not isinstance(msg, dict) or "id" not in msg else _error(msg.get("id"), -32600, "Invalid Request")
        method, mid, params = msg["method"], msg.get("id"), msg.get("params") or {}
        if mid is None:
            return None  # notifications (initialized, cancelled) need no reply
        try:
            if method == "initialize":
                return _result(mid, self._initialize(params))
            if method == "ping":
                return _result(mid, {})
            if method == "tools/list":
                return _result(mid, {"tools": [{"name": n, "description": d, "inputSchema": s} for n, (d, s, _) in self.tools.items()]})
            if method == "tools/call":
                return _result(mid, self._call_tool(params))
            if method == "resources/list":
                return _result(mid, {"resources": RESOURCES})
            if method == "resources/templates/list":
                return _result(mid, {"resourceTemplates": RESOURCE_TEMPLATES})
            if method == "resources/read":
                return _result(mid, self._read_resource(str(params.get("uri", ""))))
            if method == "prompts/list":
                return _result(mid, {"prompts": [{"name": n, "description": p["description"], "arguments": p["arguments"]} for n, p in PROMPTS.items()]})
            if method == "prompts/get":
                return _result(mid, self._get_prompt(params))
            return _error(mid, -32601, f"Method not found: {method}")
        except _InvalidParams as e:
            return _error(mid, -32602, str(e))
        except Exception as e:  # never leak a traceback or secret to the client
            return _error(mid, -32603, scrub_secrets(f"{type(e).__name__}: {e}"))

    def _initialize(self, params: Dict[str, Any]) -> Dict[str, Any]:
        requested = params.get("protocolVersion")
        self.protocol_version = requested if requested in SUPPORTED_PROTOCOL_VERSIONS else DEFAULT_PROTOCOL_VERSION
        return {
            "protocolVersion": self.protocol_version,
            "capabilities": {"tools": {"listChanged": False}, "resources": {"listChanged": False, "subscribe": False}, "prompts": {"listChanged": False}},
            "serverInfo": SERVER_INFO,
            "instructions": (
                "Runport benchmarks AI targets under spend caps. Plans are free to create; live execution needs a person to approve "
                "the plan with `runport approve <plan_id>` or in the Web UI. You cannot approve plans."
            ),
        }

    def _call_tool(self, params: Dict[str, Any]) -> Dict[str, Any]:
        name = params.get("name")
        if name not in self.tools:
            raise _InvalidParams(f"Unknown tool: {name}")
        _, schema, fn = self.tools[name]
        args = params.get("arguments") or {}
        errors, _ = validate_json_schema(args, schema)
        if errors:  # reported as a tool error so the calling model can correct its arguments
            return {"content": [{"type": "text", "text": "Invalid arguments: " + "; ".join(errors)}], "isError": True}
        try:
            payload = scrub_secrets(fn(args))
        except ToolError as e:
            return {"content": [{"type": "text", "text": scrub_secrets(str(e))}], "isError": True}
        text = json.dumps(payload, indent=2, default=str)
        result: Dict[str, Any] = {"content": [{"type": "text", "text": text}], "isError": False}
        if self.protocol_version != "2024-11-05" and isinstance(payload, dict):
            result["structuredContent"] = json.loads(text)
        return result

    # ------------------------------------------------------------------ tools

    def _svc(self) -> Any:
        return self._service_factory()

    def _list_connectors(self, _: Dict[str, Any]) -> Dict[str, Any]:
        from dataclasses import asdict

        from runport.connectors.registry import CONNECTOR_MATRIX

        return {"connectors": [asdict(c) for c in CONNECTOR_MATRIX]}

    def _list_models(self, _: Dict[str, Any]) -> Dict[str, Any]:
        from runport.models.catalog import get_portfolio

        return {
            "models": [
                {
                    "model_id": m.model_id,
                    "display_name": m.display_name,
                    "input_price_per_1m_usd": str(m.input_price_per_1m_usd),
                    "output_price_per_1m_usd": str(m.output_price_per_1m_usd),
                    "verification_status": m.verification_status,
                }
                for m in get_portfolio()
            ]
        }

    def _list_targets(self, _: Dict[str, Any]) -> Dict[str, Any]:
        from runport.targets.base import billing_for_url

        out = []
        for tid, spec in self._svc().workspace_target_specs().items():
            url = spec.get("url") or spec.get("base_url")
            out.append(
                {
                    "target_id": tid,
                    "type": spec.get("type"),
                    "billing": spec.get("billing") or (billing_for_url(url).value if url else "local"),
                    "header_names": sorted((spec.get("headers") or {}).keys()),
                    "priced": bool(spec.get("pricing")),
                }
            )
        return {"targets": out}

    def _list_datasets(self, _: Dict[str, Any]) -> Dict[str, Any]:
        from runport.core.config import settings

        d_dir = settings.workspace_root / "data" / "evaluation"
        sets = []
        for f in sorted(d_dir.glob("*.jsonl")) if d_dir.is_dir() else []:
            with open(f, "r", encoding="utf-8") as fh:
                n = sum(1 for line in fh if line.strip() and not line.startswith("#"))
            sets.append({"dataset_name": f.name, "case_count": n})
        return {"datasets": sets}

    def _known_target(self, svc: Any, tid: str) -> None:
        from runport.models.catalog import get_portfolio

        if tid not in svc.workspace_target_specs() and tid not in {m.model_id for m in get_portfolio()}:
            raise ToolError(f"Unknown target '{tid}'. Use list_targets or list_models; agents cannot define new targets.")

    def _validate_target(self, args: Dict[str, Any]) -> Dict[str, Any]:
        svc = self._svc()
        self._known_target(svc, args["target_id"])
        try:
            targets, specs = svc.resolve([args["target_id"]])
        except Exception as e:
            raise ToolError(f"Target cannot be built: {e}") from e
        t = targets[args["target_id"]]
        return {
            "target_id": t.target_id,
            "type": specs[t.target_id].get("type"),
            "billing": t.billing.value,
            "priced": t.pricing is not None,
            "capabilities": list(t.capabilities),
            "sent_requests": 0,
        }

    def _create_plan(self, args: Dict[str, Any]) -> Dict[str, Any]:
        from runport.services.execution import load_dataset_cases, resolve_dataset

        svc = self._svc()
        for tid in args["target_ids"]:
            self._known_target(svc, tid)
        try:
            cases = load_dataset_cases(resolve_dataset(args["dataset_name"]), args.get("sample_size"))
            targets, specs = svc.resolve(args["target_ids"])
        except (OSError, ValueError) as e:
            raise ToolError(str(e)) from e
        plan = svc.plan(
            targets,
            specs,
            cases,
            dataset_label=args["dataset_name"],
            requested_by="mcp",
            source={"dataset_name": args["dataset_name"], "sample_size": args.get("sample_size")},
        )
        out = plan.to_dict()
        out["next_step"] = f"Ask a person to approve: `runport approve {plan.plan_id}` (or the Web UI). Then call execute_approved_benchmark."
        return out

    def _plan_or_error(self, plan_id: str) -> Any:
        plan = self._svc().get_plan(plan_id)
        if plan is None:
            raise ToolError(f"No plan '{plan_id}'.")
        return plan

    def _request_approval(self, args: Dict[str, Any]) -> Dict[str, Any]:
        plan = self._plan_or_error(args["plan_id"])
        return {
            "plan_id": plan.plan_id,
            "status": plan.status,
            "approved": plan.status == "APPROVED",
            "blockers": plan.blockers,
            "how_to_approve": [f"Terminal: runport approve {plan.plan_id}", f"Web UI: approve the plan with fingerprint {plan.fingerprint[:16]}…"],
            "note": "This tool does not approve anything. Only a person can approve live spend.",
        }

    def _plan_status(self, args: Dict[str, Any]) -> Dict[str, Any]:
        return self._plan_or_error(args["plan_id"]).to_dict()

    def _execute(self, args: Dict[str, Any]) -> Dict[str, Any]:
        from runport.core.budget import BudgetExceededError
        from runport.providers.base import ConfidentialityViolationError, LiveNotAuthorizedError
        from runport.services.execution import load_dataset_cases, resolve_dataset, rubric_case_scorer

        svc = self._svc()
        plan = svc.get_plan(args["plan_id"])
        if plan is None:
            raise ToolError(f"No plan '{args['plan_id']}'.")
        if plan.status != "APPROVED":
            raise ToolError(f"Plan is {plan.status}; a person must approve it first (runport approve {plan.plan_id}).")
        source = plan.source or {}
        if not source.get("dataset_name"):
            raise ToolError("This plan was not created through MCP and cannot be executed from here.")
        try:
            cases = load_dataset_cases(resolve_dataset(source["dataset_name"]), source.get("sample_size"))
            outcome = svc.execute_by_ids(plan.plan_id, cases, case_scorer=rubric_case_scorer)
        except (LiveNotAuthorizedError, BudgetExceededError, ConfidentialityViolationError, OSError, ValueError) as e:
            raise ToolError(f"Not executed: {e}") from e
        return {
            "plan_id": outcome.plan_id,
            "runs": [
                {
                    "run_id": r.run_id,
                    "target_id": r.target_id,
                    "successful_cases": r.successful_cases,
                    "failed_cases": r.failed_cases,
                    "skipped_cases": r.skipped_cases,
                    "booked_spend_usd": str(r.total_spend_usd),
                    "mean_latency_ms": r.mean_latency_ms,
                    "halted_reason": r.halted_reason,
                    "halt_kind": r.halt_kind,
                }
                for r in outcome.runs
            ],
        }

    def _get_run(self, args: Dict[str, Any]) -> Dict[str, Any]:
        run = self._svc().db.get_evaluation_run(args["run_id"])
        if not run:
            raise ToolError(f"No run '{args['run_id']}'.")
        return {"run": run}

    def _get_results(self, args: Dict[str, Any]) -> Dict[str, Any]:
        rows = self._svc().db.get_evaluation_results_for_run(args["run_id"])
        if args.get("only_failures"):
            rows = [r for r in rows if not r.get("generated_output") or (r.get("accuracy") is not None and r["accuracy"] < 0.5)]
        return {"run_id": args["run_id"], "results": rows[: int(args.get("limit") or 100)], "total": len(rows)}

    def _compare(self, args: Dict[str, Any]) -> Dict[str, Any]:
        db = self._svc().db
        a, b = db.get_evaluation_run(args["run_a"]), db.get_evaluation_run(args["run_b"])
        if not a or not b:
            raise ToolError("Both runs must exist.")
        keys = ["model_id", "total_cases", "completed_cases", "failed_cases", "total_cost_usd", "mean_latency_ms", "mean_accuracy", "mean_overall_score"]
        return {"run_a": {k: a.get(k) for k in keys}, "run_b": {k: b.get(k) for k in keys}, "note": "Unmeasured metrics are null, not zero."}

    def _list_jobs(self, args: Dict[str, Any]) -> Dict[str, Any]:
        from runport.api.v1.jobs import JobManager

        limit = int(args.get("limit") or 50)
        jobs = JobManager().list_jobs(limit=limit)
        return {"jobs": jobs}

    def _cancel_job(self, args: Dict[str, Any]) -> Dict[str, Any]:
        from runport.api.v1.jobs import JobManager

        try:
            job = JobManager().cancel_job(args["job_id"])
            return {"job": job}
        except Exception as e:
            raise ToolError(f"Could not cancel job: {e}") from e

    # ------------------------------------------------------------------ resources and prompts

    def _read_resource(self, uri: str) -> Dict[str, Any]:
        fixed: Dict[str, Callable[[], Any]] = {
            "runport://connectors": lambda: self._list_connectors({}),
            "runport://models": lambda: self._list_models({}),
            "runport://targets": lambda: self._list_targets({}),
            "runport://datasets": lambda: self._list_datasets({}),
            "runport://runs": lambda: {"runs": self._svc().db.get_all_evaluation_runs(limit=50)},
            "runport://budget": self._budget,
        }
        if uri in fixed:
            data = fixed[uri]()
        elif uri.startswith("runport://runs/") and len(uri) > len("runport://runs/"):
            try:
                data = {**self._get_run({"run_id": uri.rsplit("/", 1)[1]}), **self._get_results({"run_id": uri.rsplit("/", 1)[1]})}
            except ToolError as e:
                raise _InvalidParams(str(e)) from e
        else:
            raise _InvalidParams(f"Unknown resource: {uri}")
        return {"contents": [{"uri": uri, "mimeType": "application/json", "text": json.dumps(scrub_secrets(data), indent=2, default=str)}]}

    def _budget(self) -> Dict[str, Any]:
        st = self._svc().budget_service.get_status()
        return {
            "total_ceiling_usd": str(st.total_ceiling_usd),
            "cumulative_spend_usd": str(st.cumulative_spend_usd),
            "remaining_total_usd": str(st.remaining_total_usd),
            "unresolved_spend_count": st.unresolved_spend_count,
        }

    def _get_prompt(self, params: Dict[str, Any]) -> Dict[str, Any]:
        name = params.get("name")
        if name not in PROMPTS:
            raise _InvalidParams(f"Unknown prompt: {name}")
        p = PROMPTS[name]
        args = params.get("arguments") or {}
        missing = [a["name"] for a in p["arguments"] if a.get("required") and a["name"] not in args]
        if missing:
            raise _InvalidParams(f"Missing prompt arguments: {', '.join(missing)}")
        return {"description": p["description"], "messages": [{"role": "user", "content": {"type": "text", "text": p["template"].format(**args)}}]}

    # ------------------------------------------------------------------ stdio loop

    def serve_stdio(self, stdin: IO[str] = sys.stdin, stdout: IO[str] = sys.stdout) -> None:
        for line in stdin:
            line = line.strip()
            if not line:
                continue
            try:
                msg = json.loads(line)
            except ValueError:
                reply: Optional[Dict[str, Any]] = _error(None, -32700, "Parse error")
            else:
                reply = self.handle(msg)
            if reply is not None:
                stdout.write(json.dumps(reply, default=str) + "\n")
                stdout.flush()


class _InvalidParams(Exception):
    pass


def _result(mid: Any, result: Dict[str, Any]) -> Dict[str, Any]:
    return {"jsonrpc": "2.0", "id": mid, "result": result}


def _error(mid: Any, code: int, message: str) -> Dict[str, Any]:
    return {"jsonrpc": "2.0", "id": mid, "error": {"code": code, "message": message}}


RESOURCES = [
    {"uri": "runport://connectors", "name": "connectors", "description": "Connector capability matrix", "mimeType": "application/json"},
    {"uri": "runport://models", "name": "models", "description": "Catalog models and pricing", "mimeType": "application/json"},
    {"uri": "runport://targets", "name": "targets", "description": "Workspace targets (no secrets)", "mimeType": "application/json"},
    {"uri": "runport://datasets", "name": "datasets", "description": "Evaluation datasets", "mimeType": "application/json"},
    {"uri": "runport://runs", "name": "runs", "description": "Recent runs", "mimeType": "application/json"},
    {"uri": "runport://budget", "name": "budget", "description": "Spend against ceilings, unresolved entries", "mimeType": "application/json"},
]
RESOURCE_TEMPLATES = [{"uriTemplate": "runport://runs/{run_id}", "name": "run", "description": "One run with per-case results", "mimeType": "application/json"}]

PROMPTS: Dict[str, Dict[str, Any]] = {
    "benchmark_target": {
        "description": "Plan a benchmark of one target on one dataset and hand approval to a person.",
        "arguments": [{"name": "target_id", "required": True}, {"name": "dataset_name", "required": True}],
        "template": (
            "Benchmark the Runport target '{target_id}' on dataset '{dataset_name}'. Call validate_target, then create_benchmark_plan. "
            "Report the worst-case spend and any blockers, then call request_benchmark_approval and tell me the exact command to approve. "
            "Do not try to approve it yourself. After I approve, call execute_approved_benchmark and summarise the results; "
            "treat null metrics as unmeasured, never as zero."
        ),
    },
    "investigate_failed_cases": {
        "description": "Read the failing cases of a run and group them by likely cause.",
        "arguments": [{"name": "run_id", "required": True}],
        "template": "Call get_evaluation_results for run '{run_id}' with only_failures=true. Group the failures by likely cause and quote the evidence for each group.",
    },
    "compare_candidates": {
        "description": "Compare two runs and say which is better on which metric.",
        "arguments": [{"name": "run_a", "required": True}, {"name": "run_b", "required": True}],
        "template": (
            "Call compare_runs for '{run_a}' and '{run_b}'. Compare accuracy, latency and booked spend. "
            "Say where a difference is too small to matter and never treat model agreement as correctness."
        ),
    },
}


def main() -> None:
    RunportMcpServer().serve_stdio()


if __name__ == "__main__":
    main()

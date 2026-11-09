"""Python SDK: benchmark an existing function, workspace target or catalog model without restructuring a project.

    from runport.sdk import benchmark

    def my_agent(case):                      # your existing code, unchanged
        return answer(case["query"])

    result = benchmark(my_agent, "evals/cases.jsonl")      # local callable: approved automatically (no spend possible)
    print(result.runs[0].successful_cases)

Anything that may leave the machine (a remote URL, a hosted model) needs a person to approve the exact plan:

    p = plan("support-agent", "evals/cases.jsonl")        # runport.yaml target or catalog model id
    approve_interactively(p)                               # typed phrase in a terminal, bound to the fingerprint
    outcome = execute(p)

Every path goes through ExecutionService and GenericRunner: plan fingerprint, approval, privacy gate, budget
preflight, persistence and spend booking are the same as in the CLI and Web UI. Replay is separate (runs/replay.py).
"""

from __future__ import annotations

import inspect
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, List, Mapping, Optional, Sequence, Union

from runport.connectors.python_target import PythonCallableTarget
from runport.services.execution import ExecutionOutcome, ExecutionService, PlanSummary, load_dataset_cases, rubric_case_scorer
from runport.targets.base import Target

TargetLike = Union[str, Target, Callable[[Dict[str, Any]], Any]]
DatasetLike = Union[str, Path, Sequence[Mapping[str, Any]]]


@dataclass
class SdkPlan:
    summary: PlanSummary
    targets: Dict[str, Target]
    specs: Dict[str, Dict[str, Any]]
    cases: List[Dict[str, Any]]
    service: ExecutionService

    @property
    def plan_id(self) -> str:
        return self.summary.plan_id

    @property
    def fingerprint(self) -> str:
        return self.summary.fingerprint


def _cases(dataset: DatasetLike, sample_size: Optional[int]) -> List[Dict[str, Any]]:
    if isinstance(dataset, (str, Path)):
        return load_dataset_cases(Path(dataset), sample_size)
    cases = [dict(c) for c in dataset]
    return cases[:sample_size] if sample_size else cases


def _target(target: TargetLike, target_id: Optional[str], service: ExecutionService) -> tuple[Dict[str, Target], Dict[str, Dict[str, Any]]]:
    if isinstance(target, str):
        return service.resolve([target])
    if isinstance(target, Target):
        tid = target.target_id
        return {tid: target}, {tid: {"type": "sdk_target", "class": f"{type(target).__module__}.{type(target).__qualname__}", "target_id": tid}}
    if callable(target):
        tid = str(target_id or getattr(target, "__name__", "callable"))
        try:
            source_ref = f"{target.__module__}:{target.__qualname__}"
            digest = json.dumps({"source": inspect.getsource(target)})
        except (OSError, TypeError, AttributeError):
            source_ref, digest = repr(target), ""
        t = PythonCallableTarget(target_id=tid, name=tid, func=target)
        return {tid: t}, {tid: {"type": "python", "callable": source_ref, "source_digest": digest}}
    raise TypeError("target must be a workspace/catalog id, a Target, or a callable")


def plan(
    target: TargetLike,
    dataset: DatasetLike,
    *,
    target_id: Optional[str] = None,
    sample_size: Optional[int] = None,
    service: Optional[ExecutionService] = None,
    project_id: str = "default",
) -> SdkPlan:
    """Creates a fingerprinted plan with projected worst-case spend and blockers. Sends nothing."""
    service = service or ExecutionService()
    targets, specs = _target(target, target_id, service)
    cases = _cases(dataset, sample_size)
    label = str(dataset) if isinstance(dataset, (str, Path)) else "in-memory cases"
    summary = service.plan(targets, specs, cases, dataset_label=label, requested_by="sdk", project_id=project_id)
    return SdkPlan(summary, targets, specs, cases, service)


def approve_interactively(p: SdkPlan) -> None:
    """A person types the confirmation phrase bound to this plan's fingerprint. Refused when not in a terminal."""
    import getpass

    from runport.core.live_guard import confirm_live_run

    projected = p.summary.projected_max_cost_usd
    confirm_live_run(
        p.summary.target_ids,
        [f"Plan {p.plan_id}: {p.summary.case_count} case(s); worst-case spend {'$%.4f' % projected if projected is not None else 'unknown'}."],
        plan_fingerprint=p.fingerprint,
    )
    p.service.approve(p.plan_id, p.fingerprint, channel="cli_interactive", approver=getpass.getuser())


def approve_with_ci_token(p: SdkPlan, token: str) -> None:
    """CI approval: requires approver.token_approver_enabled in runport.yaml and a token equal to the plan fingerprint."""
    from runport.core.approvers import TokenApprover

    TokenApprover(token=token, enabled=p.service.workspace.approver.token_approver_enabled).request_approval(plan_fingerprint=p.fingerprint)
    p.service.approve(p.plan_id, p.fingerprint, channel="ci_token", approver="ci")


def execute(p: SdkPlan, *, score: bool = True) -> ExecutionOutcome:
    """Executes an approved plan once through GenericRunner."""
    return p.service.execute(p.plan_id, p.targets, p.specs, p.cases, case_scorer=rubric_case_scorer if score else None)


def benchmark(
    target: TargetLike,
    dataset: DatasetLike,
    *,
    target_id: Optional[str] = None,
    sample_size: Optional[int] = None,
    score: bool = True,
    service: Optional[ExecutionService] = None,
    project_id: str = "default",
) -> ExecutionOutcome:
    """Plan, approve and execute in one call.

    Plans whose every target is local (a Python callable, a subprocess, a loopback URL) are approved through the
    `local_only` channel: nothing leaves the machine and nothing can bill. Any other plan asks for the typed
    phrase in the terminal and is refused when there is no terminal.
    """
    p = plan(target, dataset, target_id=target_id, sample_size=sample_size, service=service, project_id=project_id)
    if p.summary.blockers:
        raise RuntimeError("Plan is blocked: " + "; ".join(p.summary.blockers))
    if all(t.get("billing") == "local" for t in p.summary.per_target):
        p.service.approve(p.plan_id, p.fingerprint, channel="local_only", approver="sdk")
    else:
        approve_interactively(p)
    return execute(p, score=score)


__all__ = ["SdkPlan", "approve_interactively", "approve_with_ci_token", "benchmark", "execute", "plan"]

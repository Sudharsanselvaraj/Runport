"""Targets management and testing API endpoints.

`POST /targets/test` sends one real request to a target, which may be billed. It therefore runs through the
same guarded path as every live benchmark (GenericRunner): authorization bound to a plan fingerprint, the
unresolved-spend block, the privacy gate, budget preflight, persistence and spend booking. A call without a
matching approval token sends nothing and answers 428 with the plan to approve.
"""

import hashlib
import json
import secrets
from collections import OrderedDict
from decimal import Decimal
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from runport.core.approvers import TokenApprover
from runport.core.budget import BudgetExceededError, BudgetService
from runport.core.config import settings
from runport.core.workspace import load_workspace_config
from runport.providers.base import LiveNotAuthorizedError, scrub_secrets
from runport.runs.executor import GenericRunner
from runport.runs.planner import ExecutionPlan
from runport.storage.db import DatabaseManager

from runport.models.catalog import get_portfolio, ModelCandidate
from runport.connectors import (
    FlowiseConnector,
    HttpWorkflowConnector,
    LangGraphConnector,
    LangflowConnector,
    N8nConnector,
    OpenAICompatConnector,
)
from runport.targets.base import CostBasis, TargetPricing, TargetResult, TargetStatus, TargetType

router = APIRouter(prefix="/targets", tags=["targets"])


class TargetPricingPayload(BaseModel):
    input_usd_per_1m: Optional[Decimal] = None
    output_usd_per_1m: Optional[Decimal] = None
    fixed_usd_per_request: Optional[Decimal] = None


class TargetDefinition(BaseModel):
    target_id: str
    name: str
    target_type: str
    provider: Optional[str] = None
    url: Optional[str] = None
    model: Optional[str] = None
    api_key: Optional[str] = None
    pricing: Optional[TargetPricingPayload] = None
    custom_headers: Optional[Dict[str, str]] = None
    payload_template: Optional[Dict[str, Any]] = None
    output_path: Optional[str] = None


class TestTargetRequest(BaseModel):
    target: TargetDefinition
    input_payload: Dict[str, Any] = Field(default_factory=lambda: {"query": "Hello, Runport benchmark test!"})
    approve_token: Optional[str] = None
    plan_nonce: Optional[str] = None


# Each 428 issues a fresh nonce that is bound into the plan fingerprint and can be redeemed once.
_PENDING_NONCES: "OrderedDict[str, None]" = OrderedDict()
_MAX_PENDING_NONCES = 256


def _issue_nonce() -> str:
    nonce = secrets.token_hex(12)
    _PENDING_NONCES[nonce] = None
    while len(_PENDING_NONCES) > _MAX_PENDING_NONCES:
        _PENDING_NONCES.popitem(last=False)
    return nonce


@router.get("", response_model=List[Dict[str, Any]])
def list_targets() -> List[Dict[str, Any]]:
    """Returns available targets across catalog models and connectors."""
    targets = []
    for m in get_portfolio():
        targets.append(
            {
                "target_id": m.model_id,
                "name": m.display_name,
                "target_type": TargetType.RAW_MODEL.value,
                "provider": m.provider,
                "license": m.license,
                "context_length": m.context_length,
                "input_price_per_1m_usd": float(m.input_price_per_1m_usd),
                "output_price_per_1m_usd": float(m.output_price_per_1m_usd),
                "verification_status": m.verification_status,
            }
        )
    return targets


def _build_connector(t: TargetDefinition, pricing: Optional[TargetPricing]) -> Any:
    ttype = t.target_type.lower()
    if ttype in (TargetType.WORKFLOW_HTTP.value, "http", "http_workflow"):
        if not t.url:
            raise HTTPException(status_code=400, detail="URL required for HTTP workflow target")
        return HttpWorkflowConnector(
            target_id=t.target_id,
            name=t.name,
            url=t.url,
            headers=t.custom_headers,
            payload_template=t.payload_template,
            output_path=t.output_path,
            pricing=pricing,
        )
    if ttype in (TargetType.RAW_MODEL.value, "openai_compat"):
        return OpenAICompatConnector(
            target_id=t.target_id,
            name=t.name,
            model=t.model or t.target_id,
            base_url=t.url or "https://api.openai.com/v1",
            api_key=t.api_key,
            custom_headers=t.custom_headers,
            pricing=pricing,
        )
    if ttype in (TargetType.WORKFLOW_FLOWISE.value, "flowise"):
        if not t.url or not t.model:
            raise HTTPException(status_code=400, detail="Flowise needs 'url' (base URL) and 'model' (chatflow id)")
        return FlowiseConnector(target_id=t.target_id, name=t.name, base_url=t.url, chatflow_id=t.model, api_key=t.api_key, pricing=pricing)
    if ttype in (TargetType.WORKFLOW_LANGFLOW.value, "langflow"):
        if not t.url or not t.model:
            raise HTTPException(status_code=400, detail="Langflow needs 'url' (base URL) and 'model' (flow id)")
        return LangflowConnector(target_id=t.target_id, name=t.name, base_url=t.url, flow_id=t.model, api_key=t.api_key, pricing=pricing)
    if ttype in (TargetType.WORKFLOW_N8N.value, "n8n"):
        if not t.url:
            raise HTTPException(status_code=400, detail="URL required for n8n connector")
        return N8nConnector(target_id=t.target_id, name=t.name, webhook_url=t.url, auth_header=t.custom_headers, pricing=pricing)
    if ttype in (TargetType.WORKFLOW_LANGGRAPH.value, "langgraph"):
        if not t.url:
            raise HTTPException(status_code=400, detail="URL required for LangGraph connector")
        return LangGraphConnector(target_id=t.target_id, name=t.name, base_url=t.url, assistant_id=t.model or "agent", api_key=t.api_key, pricing=pricing)
    raise HTTPException(status_code=400, detail=f"Unsupported target type '{t.target_type}'")


def _sha256_json(obj: Any) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True, default=str).encode("utf-8")).hexdigest()


def _test_plan(t: TargetDefinition, input_payload: Dict[str, Any], per_case_cap: Decimal, nonce: str) -> ExecutionPlan:
    """One-case live plan. The fingerprint binds the target definition, the payload, the spend cap and a single-use nonce.

    Secret values are not hashed into the plan; only whether a key is present and which header names are set,
    so the fingerprint can be shown and logged without leaking anything.
    """
    definition = t.model_dump(exclude={"api_key", "custom_headers"}, mode="json")
    definition["has_api_key"] = bool(t.api_key)
    definition["header_names"] = sorted((t.custom_headers or {}).keys())
    return ExecutionPlan(
        plan_id=f"target-test-{t.target_id}",
        target_ids=[t.target_id],
        dataset_path="api:targets/test",
        dataset_hash=_sha256_json({"payload": input_payload, "nonce": nonce}),
        total_cases=1,
        budget_cap_usd=per_case_cap,
        prompt_template_hash=_sha256_json(definition),
        is_live=True,
    )


@router.post("/test", response_model=Dict[str, Any])
def test_target(req: TestTargetRequest) -> Dict[str, Any]:
    """Sends one guarded live request to a target.

    Step 1: call without `approve_token` -> 428 with `plan_fingerprint` and `plan_nonce`; nothing is sent.
    Step 2: call again with the same target and payload, `plan_nonce`, and `approve_token` set to the fingerprint
    (or the `approval-<fp[:16]>` token from `POST /api/runs/approve`) -> the request runs through GenericRunner
    and its spend is booked. A nonce is redeemable once; any mismatch answers 428 with a fresh plan.
    """
    t = req.target
    pricing = None
    if t.pricing:
        pricing = TargetPricing(
            input_usd_per_1m=t.pricing.input_usd_per_1m,
            output_usd_per_1m=t.pricing.output_usd_per_1m,
            fixed_usd_per_request=t.pricing.fixed_usd_per_request,
        )
    connector = _build_connector(t, pricing)

    workspace = load_workspace_config()
    token = (req.approve_token or "").strip()
    nonce = (req.plan_nonce or "").strip()
    plan = _test_plan(t, req.input_payload, workspace.budget.per_case_usd, nonce) if nonce in _PENDING_NONCES else None
    if plan is None or token not in (plan.fingerprint, f"approval-{plan.fingerprint[:16]}"):
        fresh_nonce = _issue_nonce()
        fresh = _test_plan(t, req.input_payload, workspace.budget.per_case_usd, fresh_nonce)
        raise HTTPException(
            status_code=428,
            detail={
                "status": "approval_required",
                "message": "Testing a target sends a real, possibly billed request. Approve this exact plan to send it."
                if not token
                else "Approval does not match a pending plan for this target and payload; nothing was sent.",
                "plan_fingerprint": fresh.fingerprint,
                "plan_nonce": fresh_nonce,
                "expected_confirmation_phrase": f"RUN LIVE {t.target_id} PLAN {fresh.fingerprint}",
                "per_case_cap_usd": f"{fresh.budget_cap_usd:.2f}",
            },
        )
    _PENDING_NONCES.pop(nonce, None)  # single use, consumed before anything is sent

    settings.ensure_directories()
    db = DatabaseManager(settings.db_path)
    db.init_db()
    runner = GenericRunner(budget_service=BudgetService(db=db, policy=settings.budget), db=db, workspace=workspace)
    case = {"id": "target-test", **req.input_payload}
    try:
        run = runner.execute_plan(plan, {t.target_id: connector}, [case], approver=TokenApprover(token=plan.fingerprint, enabled=True, operator="Web UI"))[0]
    except LiveNotAuthorizedError as e:
        raise HTTPException(status_code=403, detail=scrub_secrets(str(e))) from e
    except BudgetExceededError as e:
        raise HTTPException(status_code=402, detail=scrub_secrets(str(e))) from e
    except ValueError as e:  # privacy gate
        raise HTTPException(status_code=400, detail=scrub_secrets(str(e))) from e

    res = run.case_results[0]
    return {
        "target_id": res.target_id,
        "run_id": run.run_id,
        "plan_fingerprint": plan.fingerprint,
        "status": res.status.value,
        "is_success": res.is_success,
        "output_text": res.output_text,
        "latency_ms": res.latency_ms,
        "tokens_in": res.tokens_in,
        "tokens_out": res.tokens_out,
        "cost_usd": str(res.cost_usd) if res.cost_usd is not None else None,
        "cost_basis": res.cost_basis.value,
        "error_message": scrub_secrets(res.error_message) if res.error_message else None,
        "error_code": res.error_code,
        "metadata": scrub_secrets(res.metadata),
    }

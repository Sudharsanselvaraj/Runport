"""Targets management and testing API endpoints.

`POST /targets/test` sends one real request to a target, which may be billed. It therefore runs through the
shared ExecutionService (plan -> approve -> execute via GenericRunner). A call without an approved plan sends
nothing and answers 428 with the plan to approve.
"""

from decimal import Decimal
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from runport.core.budget import BudgetExceededError
from runport.providers.base import ConfidentialityViolationError, LiveNotAuthorizedError, scrub_secrets
from runport.services.execution import ExecutionService
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
    approve_token: Optional[str] = Field(default=None, description="The plan fingerprint from the 428 answer")
    plan_id: Optional[str] = Field(default=None, description="The plan id from the 428 answer")
    approver: str = "Web UI"


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


def _definition_spec(t: TargetDefinition) -> Dict[str, Any]:
    """What the plan fingerprint binds: the definition without secret values (only whether they are present)."""
    spec = t.model_dump(exclude={"api_key", "custom_headers"}, mode="json")
    spec["type"] = t.target_type.lower()
    spec["has_api_key"] = bool(t.api_key)
    spec["header_names"] = sorted((t.custom_headers or {}).keys())
    return spec


@router.post("/test", response_model=Dict[str, Any])
def test_target(req: TestTargetRequest) -> Dict[str, Any]:
    """Sends one guarded live request to a target.

    Step 1: call without `plan_id` -> 428 with `plan_id`, `plan_fingerprint` and the projected spend; nothing is sent.
    Step 2: call again with the same target and payload plus `plan_id` and `approve_token` (= the fingerprint). That
    call is the Web UI approval: the plan is approved (channel web_ui) and executed once through GenericRunner.
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
    spec = _definition_spec(t)
    # Operator-typed probe text, sent only after the operator approves this exact plan.
    case = {"id": "target-probe", "classification": "SYNTHETIC", **req.input_payload}
    service = ExecutionService()

    if not req.plan_id:
        plan = service.plan({t.target_id: connector}, {t.target_id: spec}, [case], dataset_label="target probe", requested_by="web_api")
        raise HTTPException(
            status_code=428,
            detail={
                "status": "approval_required",
                "message": "Testing a target sends a real, possibly billed request. Approve this exact plan to send it.",
                **plan.to_dict(),
            },
        )

    try:
        service.approve(req.plan_id, (req.approve_token or "").strip(), channel="web_ui", approver=req.approver)
        outcome = service.execute(req.plan_id, {t.target_id: connector}, {t.target_id: spec}, [case])
    except LiveNotAuthorizedError as e:
        raise HTTPException(status_code=403, detail=scrub_secrets(str(e))) from e
    except BudgetExceededError as e:
        raise HTTPException(status_code=402, detail=scrub_secrets(str(e))) from e
    except ConfidentialityViolationError as e:
        raise HTTPException(status_code=400, detail=scrub_secrets(str(e))) from e
    except ValueError as e:  # forbidden-field privacy gate
        raise HTTPException(status_code=400, detail=scrub_secrets(str(e))) from e

    run = outcome.runs[0]
    res = run.case_results[0]
    return {
        "target_id": res.target_id,
        "run_id": run.run_id,
        "plan_id": outcome.plan_id,
        "plan_fingerprint": outcome.fingerprint,
        "status": res.status.value,
        "is_success": res.is_success,
        "output_text": res.output_text,
        "latency_ms": res.latency_ms,
        "tokens_in": res.tokens_in,
        "tokens_out": res.tokens_out,
        "cost_usd": str(res.cost_usd) if res.cost_usd is not None else None,
        "cost_basis": res.cost_basis.value,
        "halted_reason": run.halted_reason,
        "error_message": scrub_secrets(res.error_message) if res.error_message else None,
        "error_code": res.error_code,
        "metadata": scrub_secrets(res.metadata),
    }

"""Targets management and testing API endpoints."""

from decimal import Decimal
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

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


@router.post("/test", response_model=Dict[str, Any])
def test_target(req: TestTargetRequest) -> Dict[str, Any]:
    """Tests a target endpoint/model with a sample payload."""
    t = req.target
    pricing = None
    if t.pricing:
        pricing = TargetPricing(
            input_usd_per_1m=t.pricing.input_usd_per_1m,
            output_usd_per_1m=t.pricing.output_usd_per_1m,
            fixed_usd_per_request=t.pricing.fixed_usd_per_request,
        )

    connector = None
    ttype = t.target_type.lower()
    if ttype == TargetType.WORKFLOW_HTTP.value or ttype == "http":
        if not t.url:
            raise HTTPException(status_code=400, detail="URL required for HTTP workflow target")
        connector = HttpWorkflowConnector(
            target_id=t.target_id,
            name=t.name,
            url=t.url,
            headers=t.custom_headers,
            payload_template=t.payload_template,
            output_path=t.output_path,
            pricing=pricing,
        )
    elif ttype == TargetType.RAW_MODEL.value or ttype == "openai_compat":
        connector = OpenAICompatConnector(
            target_id=t.target_id,
            name=t.name,
            model=t.model or t.target_id,
            base_url=t.url or "https://api.openai.com/v1",
            api_key=t.api_key,
            custom_headers=t.custom_headers,
            pricing=pricing,
        )
    elif ttype == TargetType.WORKFLOW_FLOWISE.value or ttype == "flowise":
        if not t.url:
            raise HTTPException(status_code=400, detail="URL required for Flowise connector")
        connector = FlowiseConnector(
            target_id=t.target_id,
            name=t.name,
            api_url=t.url,
            api_key=t.api_key,
            pricing=pricing,
        )
    elif ttype == TargetType.WORKFLOW_LANGFLOW.value or ttype == "langflow":
        if not t.url:
            raise HTTPException(status_code=400, detail="URL required for Langflow connector")
        connector = LangflowConnector(
            target_id=t.target_id,
            name=t.name,
            api_url=t.url,
            api_key=t.api_key,
            pricing=pricing,
        )
    elif ttype == TargetType.WORKFLOW_N8N.value or ttype == "n8n":
        if not t.url:
            raise HTTPException(status_code=400, detail="URL required for n8n connector")
        connector = N8nConnector(
            target_id=t.target_id,
            name=t.name,
            webhook_url=t.url,
            auth_token=t.api_key,
            pricing=pricing,
        )
    elif ttype == TargetType.WORKFLOW_LANGGRAPH.value or ttype == "langgraph":
        if not t.url:
            raise HTTPException(status_code=400, detail="URL required for LangGraph connector")
        connector = LangGraphConnector(
            target_id=t.target_id,
            name=t.name,
            deployment_url=t.url,
            assistant_id=t.model or "agent",
            api_key=t.api_key,
            pricing=pricing,
        )
    else:
        raise HTTPException(status_code=400, detail=f"Unsupported target type '{t.target_type}'")

    res = connector.execute(req.input_payload)
    return {
        "target_id": res.target_id,
        "status": res.status.value,
        "is_success": res.is_success,
        "output_text": res.output_text,
        "latency_ms": res.latency_ms,
        "tokens_in": res.tokens_in,
        "tokens_out": res.tokens_out,
        "cost_usd": str(res.cost_usd) if res.cost_usd is not None else None,
        "cost_basis": res.cost_basis.value,
        "error_message": res.error_message,
        "error_code": res.error_code,
        "metadata": res.metadata,
    }

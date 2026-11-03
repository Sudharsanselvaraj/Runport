"""Flowise AI workflow connector for Runport.

Integrates with Flowise prediction endpoints (/api/v1/prediction/{chatflow_id}).
"""

from typing import Any, Dict, Optional

from runport.connectors.http_workflow import HttpWorkflowConnector
from runport.targets.base import TargetPricing, TargetType


class FlowiseConnector(HttpWorkflowConnector):
    """Benchmarks Flowise chatflow and agent workflows."""

    def __init__(
        self,
        target_id: str,
        name: str,
        base_url: str,
        chatflow_id: str,
        api_key: Optional[str] = None,
        override_config: Optional[Dict[str, Any]] = None,
        pricing: Optional[TargetPricing] = None,
        timeout_seconds: float = 60.0,
        max_retries: int = 3,
    ) -> None:
        url = f"{base_url.rstrip('/')}/api/v1/prediction/{chatflow_id}"
        headers = {}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        payload_template: Dict[str, Any] = {
            "question": "{{query}}",
        }
        if override_config:
            payload_template["overrideConfig"] = override_config

        super().__init__(
            target_id=target_id,
            name=name,
            url=url,
            method="POST",
            headers=headers,
            payload_template=payload_template,
            output_path="text",
            pricing=pricing,
            timeout_seconds=timeout_seconds,
            max_retries=max_retries,
        )
        self.target_type = TargetType.WORKFLOW_FLOWISE

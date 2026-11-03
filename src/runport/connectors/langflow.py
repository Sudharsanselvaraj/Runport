"""Langflow workflow connector for Runport.

Integrates with Langflow run endpoints (/api/v1/run/{flow_id}).
"""

from typing import Any, Dict, Optional

from runport.connectors.http_workflow import HttpWorkflowConnector
from runport.targets.base import TargetPricing, TargetType


class LangflowConnector(HttpWorkflowConnector):
    """Benchmarks Langflow visual pipelines and agent architectures."""

    def __init__(
        self,
        target_id: str,
        name: str,
        base_url: str,
        flow_id: str,
        api_key: Optional[str] = None,
        tweaks: Optional[Dict[str, Any]] = None,
        pricing: Optional[TargetPricing] = None,
        timeout_seconds: float = 60.0,
        max_retries: int = 3,
    ) -> None:
        url = f"{base_url.rstrip('/')}/api/v1/run/{flow_id}"
        headers = {}
        if api_key:
            headers["x-api-key"] = api_key

        payload_template: Dict[str, Any] = {
            "input_value": "{{query}}",
            "input_type": "chat",
            "output_type": "chat",
        }
        if tweaks:
            payload_template["tweaks"] = tweaks

        super().__init__(
            target_id=target_id,
            name=name,
            url=url,
            method="POST",
            headers=headers,
            payload_template=payload_template,
            output_path="outputs.0.outputs.0.results.message.text",
            pricing=pricing,
            timeout_seconds=timeout_seconds,
            max_retries=max_retries,
        )
        self.target_type = TargetType.WORKFLOW_LANGFLOW

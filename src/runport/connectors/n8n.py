"""n8n workflow automation connector for Runport.

Integrates with n8n production webhook triggers.
"""

from typing import Any, Dict, Optional

from runport.connectors.http_workflow import HttpWorkflowConnector
from runport.targets.base import TargetPricing, TargetType


class N8nConnector(HttpWorkflowConnector):
    """Benchmarks n8n automated agent and multi-step workflow webhooks."""

    def __init__(
        self,
        target_id: str,
        name: str,
        webhook_url: str,
        auth_header: Optional[Dict[str, str]] = None,
        output_path: Optional[str] = "output",
        pricing: Optional[TargetPricing] = None,
        timeout_seconds: float = 60.0,
        max_retries: int = 3,
    ) -> None:
        headers = auth_header or {}
        payload_template = {
            "query": "{{query}}",
            "payload": "{{payload}}",
        }

        super().__init__(
            target_id=target_id,
            name=name,
            url=webhook_url,
            method="POST",
            headers=headers,
            payload_template=payload_template,
            output_path=output_path,
            pricing=pricing,
            timeout_seconds=timeout_seconds,
            max_retries=max_retries,
        )
        self.target_type = TargetType.WORKFLOW_N8N

"""LangGraph agent architecture connector for Runport.

Integrates with LangGraph Cloud and self-hosted LangGraph Server run endpoints.
"""

from typing import Any, Dict, Optional

from runport.connectors.http_workflow import HttpWorkflowConnector
from runport.targets.base import TargetPricing, TargetType


class LangGraphConnector(HttpWorkflowConnector):
    """Benchmarks LangGraph multi-agent systems and stateful graph runs."""

    def __init__(
        self,
        target_id: str,
        name: str,
        base_url: str,
        assistant_id: str,
        api_key: Optional[str] = None,
        pricing: Optional[TargetPricing] = None,
        timeout_seconds: float = 60.0,
        max_retries: int = 3,
    ) -> None:
        url = f"{base_url.rstrip('/')}/runs/wait"
        headers = {}
        if api_key:
            headers["x-api-key"] = api_key

        payload_template = {
            "assistant_id": assistant_id,
            "input": {
                "messages": [
                    {"role": "user", "content": "{{query}}"}
                ]
            },
        }

        super().__init__(
            target_id=target_id,
            name=name,
            url=url,
            method="POST",
            headers=headers,
            payload_template=payload_template,
            output_path="messages.-1.content",
            pricing=pricing,
            timeout_seconds=timeout_seconds,
            max_retries=max_retries,
        )
        self.target_type = TargetType.WORKFLOW_LANGGRAPH


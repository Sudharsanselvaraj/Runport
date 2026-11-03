"""Structured data and entity extraction workload."""

import json
from typing import Any, Dict, List, Optional, Sequence

from runport.scorers.base import BaseScorer
from runport.scorers.extraction import FieldMatchScorer, JSONSchemaScorer
from runport.workloads.base import BaseWorkload


class ExtractionWorkload(BaseWorkload):
    """Workload for extracting structured JSON entities from unstructured text."""

    def __init__(
        self,
        name: str = "extraction",
        schema_fields: Optional[Sequence[str]] = None,
        prompt_template: str = "Extract the key information from the following text as a JSON object with fields {fields}:\n\nText: {input}\n\nJSON:",
    ):
        super().__init__(name=name, description="Structured extraction workload evaluating JSON adherence and key-value accuracy.")
        self.schema_fields = list(schema_fields or [])
        self.prompt_template = prompt_template

    def prepare_prompt(self, case: Dict[str, Any]) -> str:
        text = str(case.get("input") or case.get("text") or case.get("query") or "")
        fields_desc = ", ".join(self.schema_fields) if self.schema_fields else "all relevant attributes"
        return self.prompt_template.format(fields=fields_desc, input=text)

    def validate_output(self, raw_output: Any) -> bool:
        if raw_output is None:
            return False
        text = str(raw_output).strip()
        if text.startswith("```json"):
            text = text[7:]
        if text.startswith("```"):
            text = text[3:]
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()
        try:
            parsed = json.loads(text)
            return isinstance(parsed, dict)
        except Exception:
            return False

    def get_scorers(self) -> List[BaseScorer]:
        return [JSONSchemaScorer(required_keys=self.schema_fields), FieldMatchScorer()]

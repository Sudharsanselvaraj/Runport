"""Fixture-based replay runner for Runport benchmarks.

Replays recorded runs deterministically without network calls or provider spend.
Strictly isolates replay runs with provenance='REPLAYED' and is_replay=True.
Never records spend in the live budget ledger.
"""

from decimal import Decimal
import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from runport.targets.base import CostBasis, Target, TargetResult, TargetStatus, TargetType


class ReplayRunner:
    """Loads recorded outputs and replays them deterministically against benchmark datasets."""

    def __init__(
        self,
        fixtures: Union[str, Path, List[Dict[str, Any]]],
        target_id: Optional[str] = None,
    ) -> None:
        self.fixtures_source = str(fixtures) if isinstance(fixtures, (str, Path)) else "in_memory"
        self.records: Dict[str, Dict[str, Any]] = {}
        self.default_target_id = target_id
        self._load_fixtures(fixtures)

    def _load_fixtures(self, fixtures: Union[str, Path, List[Dict[str, Any]]]) -> None:
        items: List[Dict[str, Any]] = []
        if isinstance(fixtures, (str, Path)):
            p = Path(fixtures)
            if not p.exists():
                raise FileNotFoundError(f"Replay fixtures file not found: {p}")
            content = p.read_text(encoding="utf-8").strip()
            if not content:
                return
            if p.suffix == ".jsonl":
                for line in content.splitlines():
                    if line.strip():
                        items.append(json.loads(line))
            else:
                loaded = json.loads(content)
                items = loaded if isinstance(loaded, list) else [loaded]
        elif isinstance(fixtures, list):
            items = fixtures

        for item in items:
            case_id = str(item.get("case_id") or item.get("id") or item.get("input_id") or "")
            if case_id:
                self.records[case_id] = item
            query = item.get("query") or item.get("prompt") or item.get("input")
            if isinstance(query, str) and query:
                self.records[query.strip()] = item

    def replay_case(
        self,
        case_id: str,
        input_payload: Optional[Dict[str, Any]] = None,
        target_id: Optional[str] = None,
    ) -> TargetResult:
        """Replays a single test case from recorded fixtures.

        Guarantees:
        - provenance is explicitly 'REPLAYED'
        - is_replay is True
        - cost_usd is Decimal('0.0000') (never books spend)
        - cost_basis is CostBasis.UNAVAILABLE
        """
        tid = target_id or self.default_target_id or "replay-target"

        record = self.records.get(str(case_id))

        if not record and input_payload:
            for k in ("query", "prompt", "input", "text"):
                val = input_payload.get(k)
                if isinstance(val, str) and val.strip() in self.records:
                    record = self.records[val.strip()]
                    break

        if not record:
            return TargetResult(
                target_id=tid,
                status=TargetStatus.FAILED,
                output_text=None,
                is_replay=True,
                provenance="REPLAYED",
                cost_usd=Decimal("0.0000"),
                cost_basis=CostBasis.UNAVAILABLE,
                error_message=f"No recorded replay fixture found for case '{case_id}'",
                metadata={"case_id": case_id, "fixture_source": self.fixtures_source},
            )

        output_text = record.get("output_text") or record.get("output") or record.get("response") or record.get("text")
        latency_ms = record.get("latency_ms")  # unrecorded latency stays None, never 0
        tokens_in = record.get("tokens_in") or record.get("prompt_tokens")
        tokens_out = record.get("tokens_out") or record.get("completion_tokens")

        # A record without an output is not a successful replay, whatever its status field says.
        status_str = record.get("status")
        try:
            status = TargetStatus(status_str) if status_str is not None else TargetStatus.SUCCESS
        except ValueError:
            status = TargetStatus.SUCCESS
        if output_text is None and status == TargetStatus.SUCCESS:
            status = TargetStatus.FAILED

        return TargetResult(
            target_id=record.get("target_id") or tid,
            status=status,
            output_text=str(output_text) if output_text is not None else None,
            raw_output=record.get("raw_output") or record,
            latency_ms=float(latency_ms) if latency_ms is not None else None,
            tokens_in=int(tokens_in) if tokens_in is not None else None,
            tokens_out=int(tokens_out) if tokens_out is not None else None,
            cost_usd=Decimal("0.0000"),
            cost_basis=CostBasis.UNAVAILABLE,
            is_replay=True,
            provenance="REPLAYED",
            error_message=record.get("error_message") or (None if output_text is not None else f"Fixture for case '{case_id}' has no recorded output"),
            error_code=record.get("error_code"),
            metadata={
                "case_id": case_id,
                "fixture_source": self.fixtures_source,
                "original_cost_usd": str(record.get("cost_usd")) if record.get("cost_usd") is not None else None,
            },
        )

    def replay_dataset(
        self,
        cases: List[Dict[str, Any]],
        target_id: Optional[str] = None,
    ) -> List[TargetResult]:
        """Replays an entire dataset of cases, returning normalized TargetResults."""
        results: List[TargetResult] = []
        for case in cases:
            case_id = str(case.get("case_id") or case.get("id") or "")
            res = self.replay_case(case_id=case_id, input_payload=case, target_id=target_id)
            results.append(res)
        return results


class ReplayTarget(Target):
    """Wraps ReplayRunner as a Target instance conforming to the Target interface."""

    def __init__(
        self,
        target_id: str,
        name: str,
        fixtures: Union[str, Path, List[Dict[str, Any]]],
    ) -> None:
        super().__init__(
            target_id=target_id,
            name=name,
            target_type=TargetType.RAW_MODEL,
            capabilities=["text", "replay"],
        )
        self.runner = ReplayRunner(fixtures=fixtures, target_id=target_id)

    def execute(
        self,
        input_payload: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None,
    ) -> TargetResult:
        case_id = ""
        if context and "case_id" in context:
            case_id = str(context["case_id"])
        elif "case_id" in input_payload:
            case_id = str(input_payload["case_id"])
        elif "id" in input_payload:
            case_id = str(input_payload["id"])

        return self.runner.replay_case(
            case_id=case_id,
            input_payload=input_payload,
            target_id=self.target_id,
        )

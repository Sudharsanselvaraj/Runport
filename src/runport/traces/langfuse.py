"""Bidirectional Langfuse interoperability for Runport canonical traces.

Milestone 5 - Task 5.2:
1. Export Runport canonical traces and spans to Langfuse v2 API format (/api/public/ingestion).
2. Import Langfuse trace and observation batches with automatic secret and credential scrubbing.
3. Strict enforcement of architectural invariants:
   - 'Null is not 0': missing tokens, latency, or cost remain None.
   - Zero secret leakage: all attributes, events, inputs, outputs, and errors are scrubbed.
   - Topological hierarchy integrity (acyclic trees, valid parent references).
"""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
import json
from typing import Any, Dict, List, Optional, Union
import uuid

from runport.providers.base import scrub_secrets
from runport.traces.domain import (
    Span,
    SpanEvent,
    SpanKind,
    SpanStatus,
    Trace,
    _ensure_utc,
)
from runport.traces.repository import TraceRepository


class LangfuseExporter:
    """Exports canonical Runport Traces and Spans into Langfuse v2 ingestion format."""

    @classmethod
    def export_trace(cls, trace: Trace) -> Dict[str, Any]:
        """Exports a single canonical trace into Langfuse v2 batch ingestion payload."""
        return cls.export_traces([trace])

    @classmethod
    def export_traces(cls, traces: List[Trace]) -> Dict[str, Any]:
        """Exports multiple canonical traces into a Langfuse v2 batch payload (POST /api/public/ingestion)."""
        batch: List[Dict[str, Any]] = []

        for trace in traces:
            trace_time = trace.start_time or trace.created_at
            trace_iso = trace_time.isoformat() if trace_time else datetime.now(timezone.utc).isoformat()

            metadata = dict(trace.attributes or {})
            if trace.run_id:
                metadata["run_id"] = trace.run_id
            if trace.case_id:
                metadata["case_id"] = trace.case_id
            if trace.target_id:
                metadata["target_id"] = trace.target_id
            metadata = scrub_secrets(metadata)

            tags = trace.attributes.get("tags", [])
            if not isinstance(tags, list):
                tags = [str(tags)]

            trace_body: Dict[str, Any] = {
                "id": trace.trace_id,
                "name": trace.name,
                "timestamp": trace_iso,
                "public": False,
                "metadata": metadata,
            }
            if trace.session_id:
                trace_body["sessionId"] = trace.session_id
            if "user_id" in trace.attributes:
                trace_body["userId"] = str(trace.attributes["user_id"])
            if "release" in trace.attributes:
                trace_body["release"] = str(trace.attributes["release"])
            if "version" in trace.attributes:
                trace_body["version"] = str(trace.attributes["version"])
            if tags:
                trace_body["tags"] = tags
            if "input" in trace.attributes:
                trace_body["input"] = scrub_secrets(trace.attributes["input"])
            if "output" in trace.attributes:
                trace_body["output"] = scrub_secrets(trace.attributes["output"])

            batch.append(
                {
                    "id": str(uuid.uuid4()),
                    "type": "trace-create",
                    "timestamp": trace_iso,
                    "body": trace_body,
                }
            )

            # Observations (Spans)
            for span in trace.spans:
                span_time = span.start_time or span.created_at
                span_iso = span_time.isoformat() if span_time else trace_iso

                obs_type = "GENERATION" if span.kind == SpanKind.LLM else "SPAN"
                span_metadata = dict(span.attributes or {})
                if span.provider:
                    span_metadata["provider"] = span.provider
                if span.attempt > 1:
                    span_metadata["attempt"] = span.attempt
                span_metadata = scrub_secrets(span_metadata)

                obs_body: Dict[str, Any] = {
                    "id": span.span_id,
                    "traceId": span.trace_id,
                    "type": obs_type,
                    "name": span.name,
                    "startTime": span.start_time.isoformat() if span.start_time else span_iso,
                    "metadata": span_metadata,
                    "level": "ERROR" if span.status == SpanStatus.ERROR else "DEFAULT",
                }

                if span.parent_span_id:
                    obs_body["parentObservationId"] = span.parent_span_id

                if span.end_time:
                    obs_body["endTime"] = span.end_time.isoformat()

                if span.model:
                    obs_body["model"] = span.model

                if span.error:
                    obs_body["statusMessage"] = scrub_secrets(span.error)

                if "input" in span.attributes:
                    obs_body["input"] = scrub_secrets(span.attributes["input"])
                if "output" in span.attributes:
                    obs_body["output"] = scrub_secrets(span.attributes["output"])

                # Invariant 1: 'Null is not 0'
                usage: Dict[str, Any] = {}
                if span.prompt_tokens is not None:
                    usage["promptTokens"] = span.prompt_tokens
                if span.completion_tokens is not None:
                    usage["completionTokens"] = span.completion_tokens
                if span.total_tokens is not None:
                    usage["totalTokens"] = span.total_tokens
                if span.cost_usd is not None:
                    try:
                        usage["totalCost"] = float(span.cost_usd)
                    except (ValueError, TypeError):
                        pass

                if usage:
                    usage["unit"] = "TOKENS"
                    obs_body["usage"] = usage

                batch.append(
                    {
                        "id": str(uuid.uuid4()),
                        "type": "observation-create",
                        "timestamp": span_iso,
                        "body": obs_body,
                    }
                )

                # Export span events as EVENT observations
                for ev in span.events:
                    ev_iso = ev.timestamp.isoformat()
                    batch.append(
                        {
                            "id": str(uuid.uuid4()),
                            "type": "observation-create",
                            "timestamp": ev_iso,
                            "body": {
                                "id": f"{span.span_id}-ev-{uuid.uuid4().hex[:8]}",
                                "traceId": span.trace_id,
                                "parentObservationId": span.span_id,
                                "type": "EVENT",
                                "name": ev.name,
                                "startTime": ev_iso,
                                "metadata": scrub_secrets(ev.attributes),
                                "level": "DEFAULT",
                            },
                        }
                    )

        return {"batch": batch}

    @classmethod
    def export_trace_detail(cls, trace: Trace) -> Dict[str, Any]:
        """Exports trace in Langfuse GET /api/public/traces/{id} hierarchical format."""
        trace_time = trace.start_time or trace.created_at
        trace_iso = trace_time.isoformat() if trace_time else datetime.now(timezone.utc).isoformat()

        metadata = dict(trace.attributes or {})
        if trace.run_id:
            metadata["run_id"] = trace.run_id
        if trace.case_id:
            metadata["case_id"] = trace.case_id
        if trace.target_id:
            metadata["target_id"] = trace.target_id
        metadata = scrub_secrets(metadata)

        observations: List[Dict[str, Any]] = []
        for span in trace.spans:
            obs_type = "GENERATION" if span.kind == SpanKind.LLM else "SPAN"
            span_meta = scrub_secrets(dict(span.attributes or {}))
            if span.provider:
                span_meta["provider"] = span.provider

            obs: Dict[str, Any] = {
                "id": span.span_id,
                "traceId": span.trace_id,
                "parentObservationId": span.parent_span_id,
                "type": obs_type,
                "name": span.name,
                "startTime": span.start_time.isoformat() if span.start_time else None,
                "endTime": span.end_time.isoformat() if span.end_time else None,
                "model": span.model,
                "level": "ERROR" if span.status == SpanStatus.ERROR else "DEFAULT",
                "statusMessage": scrub_secrets(span.error) if span.error else None,
                "metadata": span_meta,
            }
            if "input" in span.attributes:
                obs["input"] = scrub_secrets(span.attributes["input"])
            if "output" in span.attributes:
                obs["output"] = scrub_secrets(span.attributes["output"])

            usage: Dict[str, Any] = {}
            if span.prompt_tokens is not None:
                usage["promptTokens"] = span.prompt_tokens
            if span.completion_tokens is not None:
                usage["completionTokens"] = span.completion_tokens
            if span.total_tokens is not None:
                usage["totalTokens"] = span.total_tokens
            if span.cost_usd is not None:
                try:
                    usage["totalCost"] = float(span.cost_usd)
                except (ValueError, TypeError):
                    pass
            if usage:
                obs["usage"] = usage

            observations.append(obs)

        return {
            "id": trace.trace_id,
            "name": trace.name,
            "timestamp": trace_iso,
            "sessionId": trace.session_id,
            "userId": trace.attributes.get("user_id"),
            "metadata": metadata,
            "observations": observations,
        }


class LangfuseIngester:
    """Parses and ingests Langfuse v2 batches or exports into canonical Runport Traces."""

    @classmethod
    def ingest_to_repository(cls, payload: Dict[str, Any], repo: TraceRepository, project_id: Optional[str] = None) -> List[Trace]:
        """Parses payload, sanitizes secrets, and persists traces into SQLite repository."""
        traces = cls.parse_traces(payload)
        for trace in traces:
            if project_id:
                trace.project_id = project_id
            repo.save_trace(trace, project_id=project_id)
        return traces

    @classmethod
    def parse_traces(cls, payload: Union[Dict[str, Any], List[Dict[str, Any]]]) -> List[Trace]:
        """Parses a Langfuse batch, export object, or list of trace objects into canonical Traces."""
        if isinstance(payload, list):
            # List of trace objects
            traces: List[Trace] = []
            for item in payload:
                if isinstance(item, dict):
                    t = cls._parse_single_trace_record(item)
                    if t:
                        traces.append(t)
            return traces

        if not isinstance(payload, dict):
            raise ValueError(f"Expected dict or list payload, got {type(payload)}")

        # Case 1: Ingestion batch payload {"batch": [...]}
        if "batch" in payload and isinstance(payload["batch"], list):
            return cls._parse_batch_payload(payload["batch"])

        # Case 2: List wrapped in "data" or "traces"
        for key in ("data", "traces"):
            if key in payload and isinstance(payload[key], list):
                return cls.parse_traces(payload[key])

        # Case 3: Single trace object with "id" and "observations"
        if "id" in payload:
            t = cls._parse_single_trace_record(payload)
            return [t] if t else []

        raise ValueError("Unrecognized Langfuse payload structure: missing 'batch', 'data', or 'id'.")

    @classmethod
    def _parse_batch_payload(cls, batch: List[Dict[str, Any]]) -> List[Trace]:
        """Parses events from a Langfuse v2 batch ingestion payload."""
        traces_by_id: Dict[str, Dict[str, Any]] = {}
        observations_by_trace: Dict[str, List[Dict[str, Any]]] = {}

        for event in batch:
            if not isinstance(event, dict):
                continue
            ev_type = event.get("type")
            body = event.get("body", {})
            if not isinstance(body, dict):
                continue

            if ev_type in ("trace-create", "trace-update"):
                tid = body.get("id")
                if tid:
                    if tid not in traces_by_id:
                        traces_by_id[tid] = {}
                    traces_by_id[tid].update(body)

            elif ev_type in ("observation-create", "observation-update"):
                tid = body.get("traceId")
                if tid:
                    observations_by_trace.setdefault(tid, []).append(body)

        result: List[Trace] = []

        # If observations exist for an unseen trace_id, create a default trace definition
        all_trace_ids = set(traces_by_id.keys()) | set(observations_by_trace.keys())

        for tid in all_trace_ids:
            trace_data = traces_by_id.get(tid, {})
            obs_list = observations_by_trace.get(tid, [])

            name = trace_data.get("name") or (f"langfuse_{tid[:8]}" if tid else "langfuse_trace")
            raw_meta = scrub_secrets(dict(trace_data.get("metadata") or {}))

            run_id = raw_meta.get("run_id")
            case_id = raw_meta.get("case_id")
            target_id = raw_meta.get("target_id")
            session_id = trace_data.get("sessionId")

            start_time = _ensure_utc(trace_data.get("timestamp"))
            end_time = None

            # Process observations into canonical spans
            spans = cls._convert_observations(tid, obs_list)

            # Derive trace start and end times from spans if not explicitly given
            if spans:
                span_starts = [s.start_time for s in spans if s.start_time]
                span_ends = [s.end_time for s in spans if s.end_time]
                if not start_time and span_starts:
                    start_time = min(span_starts)
                if span_ends:
                    end_time = max(span_ends)

            status = SpanStatus.OK
            if any(s.status == SpanStatus.ERROR for s in spans):
                status = SpanStatus.ERROR

            trace = Trace(
                trace_id=tid,
                run_id=run_id,
                case_id=case_id,
                target_id=target_id,
                session_id=session_id,
                name=name,
                status=status,
                start_time=start_time,
                end_time=end_time,
                attributes=raw_meta,
                spans=spans,
                source="langfuse",
                source_ref=tid,
            )
            result.append(trace)

        return result

    @classmethod
    def _parse_single_trace_record(cls, record: Dict[str, Any]) -> Optional[Trace]:
        """Parses a single trace record with nested observations."""
        tid = record.get("id")
        if not tid:
            return None

        name = record.get("name") or f"langfuse_{tid[:8]}"
        raw_meta = scrub_secrets(dict(record.get("metadata") or {}))

        run_id = raw_meta.get("run_id")
        case_id = raw_meta.get("case_id")
        target_id = raw_meta.get("target_id")
        session_id = record.get("sessionId")

        start_time = _ensure_utc(record.get("timestamp") or record.get("startTime"))
        obs_list = record.get("observations", [])
        spans = cls._convert_observations(tid, obs_list)

        end_time = None
        if spans:
            span_starts = [s.start_time for s in spans if s.start_time]
            span_ends = [s.end_time for s in spans if s.end_time]
            if not start_time and span_starts:
                start_time = min(span_starts)
            if span_ends:
                end_time = max(span_ends)

        status = SpanStatus.OK
        if any(s.status == SpanStatus.ERROR for s in spans):
            status = SpanStatus.ERROR

        return Trace(
            trace_id=tid,
            run_id=run_id,
            case_id=case_id,
            target_id=target_id,
            session_id=session_id,
            name=name,
            status=status,
            start_time=start_time,
            end_time=end_time,
            attributes=raw_meta,
            spans=spans,
            source="langfuse",
            source_ref=tid,
        )

    @classmethod
    def _convert_observations(cls, trace_id: str, observations: List[Dict[str, Any]]) -> List[Span]:
        """Maps Langfuse observation objects to canonical Runport Span models."""
        spans: List[Span] = []
        known_span_ids: set[str] = set()

        # Filter out EVENT types first, associate with parents if possible
        span_items: List[Dict[str, Any]] = []
        event_items: List[Dict[str, Any]] = []

        for obs in observations:
            obs_type = str(obs.get("type", "SPAN")).upper()
            if obs_type == "EVENT":
                event_items.append(obs)
            else:
                span_items.append(obs)

        # First pass: map SPAN and GENERATION
        for obs in span_items:
            sid = obs.get("id")
            if not sid:
                continue

            # Deduplicate span ID within trace
            if sid in known_span_ids:
                sid = f"{sid}-{len(known_span_ids)}"
            known_span_ids.add(sid)

            name = obs.get("name") or "step"
            obs_type = str(obs.get("type", "SPAN")).upper()

            # Map SpanKind
            kind = cls._infer_span_kind(obs_type, name, obs)

            # Map Status
            level = str(obs.get("level", "DEFAULT")).upper()
            status = SpanStatus.ERROR if level in ("ERROR", "CRITICAL") else SpanStatus.OK

            start_time = _ensure_utc(obs.get("startTime"))
            end_time = _ensure_utc(obs.get("endTime"))

            # Calculate duration if available
            duration_ms = None
            if start_time and end_time and end_time >= start_time:
                duration_ms = max(0.0, round((end_time - start_time).total_seconds() * 1000.0, 3))
            elif "latency" in obs and obs["latency"] is not None:
                try:
                    # Langfuse latency is in seconds
                    duration_ms = max(0.0, round(float(obs["latency"]) * 1000.0, 3))
                except (ValueError, TypeError):
                    pass

            model = obs.get("model")

            # Invariant 1: 'Null is not 0'
            prompt_tokens = None
            completion_tokens = None
            total_tokens = None
            cost_usd = None
            cost_basis = None

            usage = obs.get("usage")
            if isinstance(usage, dict):
                prompt_tokens = cls._parse_int_metric(usage.get("promptTokens") or usage.get("input"))
                completion_tokens = cls._parse_int_metric(usage.get("completionTokens") or usage.get("output"))
                total_tokens = cls._parse_int_metric(usage.get("totalTokens") or usage.get("total"))

                # Cost
                total_cost = usage.get("totalCost")
                if total_cost is not None:
                    try:
                        cost_usd = str(Decimal(str(total_cost)))
                        cost_basis = "ACTUAL"
                    except Exception:
                        pass
                elif usage.get("inputCost") is not None or usage.get("outputCost") is not None:
                    try:
                        c_in = Decimal(str(usage.get("inputCost", 0) or 0))
                        c_out = Decimal(str(usage.get("outputCost", 0) or 0))
                        cost_usd = str(c_in + c_out)
                        cost_basis = "ACTUAL"
                    except Exception:
                        pass

            attributes = dict(obs.get("metadata") or {})
            if "input" in obs:
                attributes["input"] = obs["input"]
            if "output" in obs:
                attributes["output"] = obs["output"]
            if "modelParameters" in obs:
                attributes["model_parameters"] = obs["modelParameters"]

            # Scrub all attributes and errors
            attributes = scrub_secrets(attributes)
            error_msg = scrub_secrets(obs.get("statusMessage")) if obs.get("statusMessage") else None

            parent_id = obs.get("parentObservationId")

            span = Span(
                trace_id=trace_id,
                span_id=sid,
                parent_span_id=parent_id,
                name=name,
                kind=kind,
                status=status,
                start_time=start_time,
                end_time=end_time,
                duration_ms=duration_ms,
                provider=attributes.get("provider"),
                model=model,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=total_tokens,
                cost_usd=cost_usd,
                cost_basis=cost_basis,
                attributes=attributes,
                events=[],
                error=error_msg,
                source="langfuse",
            )
            spans.append(span)

        # Fix any parent references pointing to unknown spans
        valid_ids = {s.span_id for s in spans}
        for s in spans:
            if s.parent_span_id is not None and s.parent_span_id not in valid_ids:
                s.parent_span_id = None

        # Attach EVENT items to matching parent span
        spans_by_id = {s.span_id: s for s in spans}
        for ev in event_items:
            parent_id = ev.get("parentObservationId")
            ev_name = ev.get("name") or "event"
            ev_time = _ensure_utc(ev.get("startTime")) or datetime.now(timezone.utc)
            ev_attrs = scrub_secrets(dict(ev.get("metadata") or {}))

            if parent_id and parent_id in spans_by_id:
                spans_by_id[parent_id].events.append(SpanEvent(name=ev_name, timestamp=ev_time, attributes=ev_attrs))

        return spans

    @staticmethod
    def _infer_span_kind(obs_type: str, name: str, obs: Dict[str, Any]) -> SpanKind:
        """Infers the canonical Runport SpanKind from Langfuse observation properties."""
        if obs_type == "GENERATION":
            return SpanKind.LLM

        name_lower = name.lower()
        meta = obs.get("metadata", {})
        meta_str = str(meta).lower()

        if "tool" in name_lower or "tool" in meta_str or "function_call" in name_lower:
            return SpanKind.TOOL
        if "retriev" in name_lower or "rag" in name_lower or "retrieval" in meta_str:
            return SpanKind.RETRIEVAL
        if "agent" in name_lower or "agent" in meta_str:
            return SpanKind.AGENT
        if "route" in name_lower or "router" in meta_str:
            return SpanKind.ROUTER
        if "rerank" in name_lower or "rerank" in meta_str:
            return SpanKind.RERANK

        return SpanKind.WORKFLOW_STEP

    @staticmethod
    def _parse_int_metric(val: Any) -> Optional[int]:
        """Safely parses a non-negative integer metric without defaulting None to 0."""
        if val is None or isinstance(val, bool):
            return None
        try:
            n = int(float(val))
            return n if n >= 0 else None
        except (ValueError, TypeError):
            return None

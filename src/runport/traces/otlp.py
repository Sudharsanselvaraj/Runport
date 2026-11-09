"""OpenTelemetry (OTel) and OpenInference interoperability for Runport.

Milestone 2 - Phase 5:
1. Ingestion of standard OTLP JSON trace payloads (`ExportTraceServiceRequest`).
2. Mapping of GenAI Semantic Conventions and OpenInference span kinds and attributes.
3. Serialization of canonical Runport Traces and Spans into standard OTLP JSON.
4. Strict enforcement of architectural invariants:
   - 'Null is not 0': missing tokens, latency, or cost remain None.
   - Zero secret leakage: all attributes, events, errors, inputs, and outputs are scrubbed.
   - Non-negative durations and counts.
   - Deterministic W3C-compliant 32-hex trace IDs and 16-hex span IDs.
"""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import re
from typing import Any, Dict, List, Optional, Tuple, Union

from runport.providers.base import scrub_secrets
from runport.traces.domain import (
    Span,
    SpanEvent,
    SpanKind,
    SpanStatus,
    Trace,
)
from runport.traces.repository import TraceRepository


# =============================================================================
# Helper Utilities: OTLP KeyValue & Datetime Parsing
# =============================================================================


def parse_otlp_value(val: Any) -> Any:
    """Recursively parses an OTLP AnyValue object into a standard Python primitive."""
    if not isinstance(val, dict):
        return val

    if "stringValue" in val:
        return val["stringValue"]
    if "intValue" in val:
        try:
            return int(val["intValue"])
        except (ValueError, TypeError):
            return val["intValue"]
    if "doubleValue" in val:
        try:
            return float(val["doubleValue"])
        except (ValueError, TypeError):
            return val["doubleValue"]
    if "boolValue" in val:
        return bool(val["boolValue"])
    if "arrayValue" in val:
        values = val.get("arrayValue", {}).get("values", [])
        return [parse_otlp_value(v) for v in values]
    if "kvlistValue" in val:
        values = val.get("kvlistValue", {}).get("values", [])
        return {item["key"]: parse_otlp_value(item.get("value")) for item in values if "key" in item}

    # If it's a generic dict with no typed field, return as-is
    return val


def parse_otlp_attributes(attrs: Any) -> Dict[str, Any]:
    """Converts OTLP KeyValue list or flat dictionary into a clean Python dictionary."""
    if isinstance(attrs, dict):
        return {k: parse_otlp_value(v) for k, v in attrs.items()}
    if isinstance(attrs, list):
        result: Dict[str, Any] = {}
        for item in attrs:
            if isinstance(item, dict) and "key" in item:
                result[item["key"]] = parse_otlp_value(item.get("value"))
        return result
    return {}


def encode_otlp_value(val: Any) -> Dict[str, Any]:
    """Encodes a Python primitive into standard OTLP AnyValue format."""
    if isinstance(val, bool):
        return {"boolValue": val}
    if isinstance(val, int):
        return {"intValue": str(val)}
    if isinstance(val, float):
        return {"doubleValue": val}
    if isinstance(val, str):
        return {"stringValue": val}
    if isinstance(val, list):
        return {"arrayValue": {"values": [encode_otlp_value(v) for v in val]}}
    if isinstance(val, dict):
        return {"kvlistValue": {"values": [{"key": str(k), "value": encode_otlp_value(v)} for k, v in val.items()]}}
    return {"stringValue": str(val)}


def encode_otlp_attributes(attrs: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Encodes a Python dictionary into an OTLP KeyValue list."""
    return [{"key": k, "value": encode_otlp_value(v)} for k, v in attrs.items() if v is not None]


def parse_unix_nano(val: Any) -> Optional[datetime]:
    """Parses nanosecond unix epoch timestamp into a timezone-aware UTC datetime."""
    if val is None or val == "" or val == 0 or val == "0":
        return None
    try:
        nano = int(val)
        if nano <= 0:
            return None
        return datetime.fromtimestamp(nano / 1_000_000_000.0, tz=timezone.utc)
    except (ValueError, TypeError, OverflowError):
        return None


def datetime_to_unix_nano(dt: Optional[datetime]) -> Optional[str]:
    """Converts a timezone-aware UTC datetime to a nanosecond unix epoch string."""
    if dt is None:
        return None
    return str(int(dt.timestamp() * 1_000_000_000))


def normalize_hex_id(id_str: str, length: int) -> str:
    """Normalizes an ID to a W3C-compliant hex string of exact length (32 for trace, 16 for span)."""
    clean = re.sub(r"[^0-9a-fA-F]", "", id_str).lower()
    if len(clean) == length:
        return clean
    # Derive deterministic hex hash
    return hashlib.sha256(id_str.encode("utf-8")).hexdigest()[:length]


# =============================================================================
# Ingestion: OTLP -> Canonical Trace & Span
# =============================================================================


def _map_span_kind(attrs: Dict[str, Any], otel_kind: int) -> SpanKind:
    """Maps OTel GenAI semantic conventions and OpenInference attributes to SpanKind."""
    # 1. OpenInference span kind
    oi_kind = str(attrs.get("openinference.span.kind", "")).upper()
    if oi_kind == "LLM":
        return SpanKind.LLM
    if oi_kind == "TOOL":
        return SpanKind.TOOL
    if oi_kind == "CHAIN":
        return SpanKind.WORKFLOW_STEP
    if oi_kind == "AGENT":
        return SpanKind.AGENT
    if oi_kind == "RETRIEVER":
        return SpanKind.RETRIEVAL
    if oi_kind == "RERANKER":
        return SpanKind.RERANK
    if oi_kind == "ROUTER":
        return SpanKind.ROUTER
    if oi_kind == "HANDOFF":
        return SpanKind.HANDOFF

    # 2. GenAI operation name
    op_name = str(attrs.get("gen_ai.operation.name", "")).lower()
    if op_name in ("chat", "completion", "generate", "text_completion"):
        return SpanKind.LLM
    if op_name in ("execute_tool", "tool", "call_tool"):
        return SpanKind.TOOL
    if op_name in ("retrieve", "retrieval", "query_index"):
        return SpanKind.RETRIEVAL
    if op_name in ("rerank", "reranker"):
        return SpanKind.RERANK
    if op_name in ("agent", "orchestrate"):
        return SpanKind.AGENT
    if op_name in ("handoff", "switch_agent"):
        return SpanKind.HANDOFF
    if op_name in ("workflow", "workflow_step", "pipeline"):
        return SpanKind.WORKFLOW_STEP

    # 3. GenAI attribute heuristic
    if "gen_ai.system" in attrs or "gen_ai.request.model" in attrs or "llm.model_name" in attrs:
        return SpanKind.LLM
    if "gen_ai.tool.name" in attrs or "tool.name" in attrs:
        return SpanKind.TOOL
    if "retrieval.documents" in attrs or "runport.retrieval.query" in attrs:
        return SpanKind.RETRIEVAL

    # 4. Fallback based on OTel span kind (3 = Client, 1 = Internal)
    if otel_kind == 3 and any("model" in k for k in attrs):
        return SpanKind.LLM

    return SpanKind.OTHER


def _map_span_status(status_obj: Optional[Dict[str, Any]]) -> Tuple[SpanStatus, Optional[str]]:
    """Maps OTel status code (0=UNSET, 1=OK, 2=ERROR) and message to SpanStatus."""
    if not status_obj:
        return SpanStatus.UNSET, None

    code = status_obj.get("code", 0)
    msg = status_obj.get("message")
    sanitized_msg = scrub_secrets(str(msg)) if msg else None

    # Handle string or int codes
    if code in (1, "STATUS_CODE_OK", "OK"):
        return SpanStatus.OK, None
    if code in (2, "STATUS_CODE_ERROR", "ERROR"):
        return SpanStatus.ERROR, sanitized_msg
    return SpanStatus.UNSET, None


def _extract_tokens(attrs: Dict[str, Any]) -> Tuple[Optional[int], Optional[int], Optional[int]]:
    """Extracts prompt, completion, and total tokens preserving 'Null is not 0' invariant."""
    prompt_tokens: Optional[int] = None
    completion_tokens: Optional[int] = None
    total_tokens: Optional[int] = None

    for k in ("gen_ai.usage.input_tokens", "gen_ai.usage.prompt_tokens", "llm.token_count.prompt", "usage.prompt_tokens"):
        if k in attrs and attrs[k] is not None:
            try:
                prompt_tokens = int(attrs[k])
                break
            except (ValueError, TypeError):
                pass

    for k in ("gen_ai.usage.output_tokens", "gen_ai.usage.completion_tokens", "llm.token_count.completion", "usage.completion_tokens"):
        if k in attrs and attrs[k] is not None:
            try:
                completion_tokens = int(attrs[k])
                break
            except (ValueError, TypeError):
                pass

    for k in ("gen_ai.usage.total_tokens", "llm.token_count.total", "usage.total_tokens"):
        if k in attrs and attrs[k] is not None:
            try:
                total_tokens = int(attrs[k])
                break
            except (ValueError, TypeError):
                pass

    return prompt_tokens, completion_tokens, total_tokens


class OtlpIngester:
    """Ingests OpenTelemetry OTLP JSON trace payloads into Runport canonical Traces."""

    @classmethod
    def parse_payload(cls, payload: Union[str, Dict[str, Any]]) -> List[Trace]:
        """Parses an ExportTraceServiceRequest payload into canonical Trace instances."""
        if isinstance(payload, str):
            payload_dict: Dict[str, Any] = json.loads(payload)
        else:
            payload_dict = payload

        resource_spans = payload_dict.get("resourceSpans", [])
        if not resource_spans:
            return []

        # Group spans by traceId
        raw_traces: Dict[str, Dict[str, Any]] = {}

        for rs in resource_spans:
            resource = rs.get("resource", {})
            resource_attrs = parse_otlp_attributes(resource.get("attributes", []))
            service_name = resource_attrs.get("service.name")

            for ss in rs.get("scopeSpans", []):
                scope = ss.get("scope", {})
                scope_name = scope.get("name")
                scope_version = scope.get("version")

                for span_data in ss.get("spans", []):
                    trace_hex = span_data.get("traceId")
                    if not trace_hex:
                        continue

                    if trace_hex not in raw_traces:
                        raw_traces[trace_hex] = {
                            "resource_attrs": resource_attrs,
                            "service_name": service_name,
                            "scope_info": {"name": scope_name, "version": scope_version},
                            "spans": [],
                        }

                    raw_traces[trace_hex]["spans"].append(span_data)

        # Build canonical Trace objects
        traces: List[Trace] = []

        for trace_hex, trace_info in raw_traces.items():
            spans_data = trace_info["spans"]
            res_attrs = trace_info["resource_attrs"]

            parsed_spans: List[Span] = []
            span_ids: set = set()

            for sd in spans_data:
                span_id_raw = sd.get("spanId", "")
                if not span_id_raw:
                    continue

                parent_id_raw = sd.get("parentSpanId")
                if parent_id_raw in ("", "0" * 16, None):
                    parent_id = None
                else:
                    parent_id = str(parent_id_raw)

                name = sd.get("name") or "unnamed_span"
                otel_kind = sd.get("kind", 0)

                # Attributes & Secret Scrubbing
                raw_attrs = parse_otlp_attributes(sd.get("attributes", []))
                scrubbed_attrs = scrub_secrets(raw_attrs)

                # Events
                parsed_events: List[SpanEvent] = []
                for ev in sd.get("events", []):
                    ev_time = parse_unix_nano(ev.get("timeUnixNano"))
                    if ev_time:
                        parsed_events.append(
                            SpanEvent(
                                name=ev.get("name") or "event",
                                timestamp=ev_time,
                                attributes=scrub_secrets(parse_otlp_attributes(ev.get("attributes", []))),
                            )
                        )

                # Timestamps
                t_start = parse_unix_nano(sd.get("startTimeUnixNano"))
                t_end = parse_unix_nano(sd.get("endTimeUnixNano"))

                # Duration
                duration_ms: Optional[float] = None
                if t_start and t_end and t_end >= t_start:
                    duration_ms = max(0.0, round((t_end - t_start).total_seconds() * 1000.0, 3))

                # Kind, Status & Error
                kind = _map_span_kind(scrubbed_attrs, otel_kind)
                status, error_msg = _map_span_status(sd.get("status"))

                # Model & Provider
                model = scrubbed_attrs.get("gen_ai.response.model") or scrubbed_attrs.get("gen_ai.request.model") or scrubbed_attrs.get("llm.model_name")
                provider = scrubbed_attrs.get("gen_ai.system") or scrubbed_attrs.get("llm.provider_name")

                # Tokens
                prompt_tokens, completion_tokens, total_tokens = _extract_tokens(raw_attrs)

                # Cost
                cost_usd = scrubbed_attrs.get("runport.cost_usd") or scrubbed_attrs.get("gen_ai.cost")
                cost_basis = scrubbed_attrs.get("runport.cost_basis")
                if cost_basis and str(cost_basis).upper() not in ("ACTUAL", "ESTIMATED", "UNRESOLVED", "UNAVAILABLE"):
                    cost_basis = None

                # Original IDs if preserved in attributes
                orig_trace_id = scrubbed_attrs.get("runport.trace_id") or trace_hex
                orig_span_id = scrubbed_attrs.get("runport.span_id") or span_id_raw
                orig_parent_id = scrubbed_attrs.get("runport.parent_span_id") or parent_id

                span = Span(
                    trace_id=orig_trace_id,
                    span_id=orig_span_id,
                    parent_span_id=orig_parent_id,
                    name=name,
                    kind=kind,
                    status=status,
                    start_time=t_start,
                    end_time=t_end,
                    duration_ms=duration_ms,
                    provider=provider,
                    model=model,
                    prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens,
                    total_tokens=total_tokens,
                    cost_usd=str(cost_usd) if cost_usd is not None else None,
                    cost_basis=str(cost_basis).upper() if cost_basis else None,
                    attributes=scrubbed_attrs,
                    events=parsed_events,
                    error=error_msg,
                    source="otel",
                )
                parsed_spans.append(span)
                span_ids.add(orig_span_id)

            if not parsed_spans:
                continue

            # Ensure parents exist within the trace, or detach orphan parents
            for s in parsed_spans:
                if s.parent_span_id is not None and s.parent_span_id not in span_ids:
                    s.parent_span_id = None

            # Trace-level metadata
            root_spans = [s for s in parsed_spans if s.parent_span_id is None]
            root_span = root_spans[0] if root_spans else parsed_spans[0]

            trace_name = root_span.name
            trace_id = root_span.trace_id

            # Determine overall trace status
            if any(s.status == SpanStatus.ERROR for s in parsed_spans):
                trace_status = SpanStatus.ERROR
            elif all(s.status == SpanStatus.OK for s in parsed_spans):
                trace_status = SpanStatus.OK
            else:
                trace_status = SpanStatus.UNSET

            t_starts = [s.start_time for s in parsed_spans if s.start_time is not None]
            t_ends = [s.end_time for s in parsed_spans if s.end_time is not None]
            trace_start = min(t_starts) if t_starts else None
            trace_end = max(t_ends) if t_ends else None

            # Trace attributes
            trace_attrs = scrub_secrets(dict(res_attrs))
            if trace_info.get("service_name"):
                trace_attrs["service.name"] = trace_info["service_name"]

            # Run and case linkage if provided in attributes
            run_id = trace_attrs.get("runport.run_id") or root_span.attributes.get("runport.run_id")
            case_id = trace_attrs.get("runport.case_id") or root_span.attributes.get("runport.case_id")
            target_id = trace_attrs.get("runport.target_id") or root_span.attributes.get("runport.target_id")

            trace = Trace(
                trace_id=trace_id,
                run_id=str(run_id) if run_id else None,
                case_id=str(case_id) if case_id else None,
                target_id=str(target_id) if target_id else None,
                name=trace_name,
                status=trace_status,
                start_time=trace_start,
                end_time=trace_end,
                attributes=trace_attrs,
                spans=parsed_spans,
                source="otel",
                source_ref=trace_hex,
            )
            traces.append(trace)

        return traces

    @classmethod
    def ingest_to_repository(cls, payload: Union[str, Dict[str, Any]], repo: TraceRepository, project_id: Optional[str] = None) -> List[Trace]:
        """Parses OTLP payload and saves all canonical traces to the repository."""
        traces = cls.parse_payload(payload)
        for t in traces:
            if project_id:
                t.project_id = project_id
            repo.save_trace(t, project_id=project_id)
        return traces


# =============================================================================
# Export: Canonical Trace & Span -> OTLP
# =============================================================================


class OtlpExporter:
    """Serializes canonical Runport Traces and Spans to standard OTLP JSON format."""

    @classmethod
    def export_trace(cls, trace: Trace, service_name: str = "runport") -> Dict[str, Any]:
        """Converts a single Trace to an ExportTraceServiceRequest dictionary."""
        return cls.export_traces([trace], service_name=service_name)

    @classmethod
    def export_traces(cls, traces: List[Trace], service_name: str = "runport") -> Dict[str, Any]:
        """Converts a collection of Traces to an ExportTraceServiceRequest dictionary."""
        resource_spans: List[Dict[str, Any]] = []

        for trace in traces:
            trace_hex = normalize_hex_id(trace.trace_id, 32)

            res_attrs = {
                "service.name": service_name,
                "telemetry.sdk.name": "runport",
                "telemetry.sdk.language": "python",
                "telemetry.sdk.version": "0.2.0",
            }
            res_attrs.update(trace.attributes)
            if trace.run_id:
                res_attrs["runport.run_id"] = trace.run_id
            if trace.case_id:
                res_attrs["runport.case_id"] = trace.case_id

            otlp_spans: List[Dict[str, Any]] = []

            for span in trace.spans:
                span_hex = normalize_hex_id(span.span_id, 16)
                parent_hex = normalize_hex_id(span.parent_span_id, 16) if span.parent_span_id else None

                # Build OTel attributes
                attrs: Dict[str, Any] = dict(span.attributes)
                attrs["runport.trace_id"] = span.trace_id
                attrs["runport.span_id"] = span.span_id
                if span.parent_span_id:
                    attrs["runport.parent_span_id"] = span.parent_span_id

                # OpenInference kind
                if span.kind == SpanKind.LLM:
                    attrs["openinference.span.kind"] = "LLM"
                    attrs["gen_ai.operation.name"] = "chat"
                elif span.kind == SpanKind.TOOL:
                    attrs["openinference.span.kind"] = "TOOL"
                    attrs["gen_ai.operation.name"] = "execute_tool"
                elif span.kind == SpanKind.RETRIEVAL:
                    attrs["openinference.span.kind"] = "RETRIEVER"
                    attrs["gen_ai.operation.name"] = "retrieve"
                elif span.kind == SpanKind.WORKFLOW_STEP:
                    attrs["openinference.span.kind"] = "CHAIN"
                elif span.kind == SpanKind.AGENT:
                    attrs["openinference.span.kind"] = "AGENT"
                elif span.kind == SpanKind.RERANK:
                    attrs["openinference.span.kind"] = "RERANKER"
                elif span.kind == SpanKind.ROUTER:
                    attrs["openinference.span.kind"] = "ROUTER"
                elif span.kind == SpanKind.HANDOFF:
                    attrs["openinference.span.kind"] = "HANDOFF"

                # GenAI semantic conventions
                if span.model:
                    attrs["gen_ai.request.model"] = span.model
                    attrs["gen_ai.response.model"] = span.model
                if span.provider:
                    attrs["gen_ai.system"] = span.provider

                # Tokens
                if span.prompt_tokens is not None:
                    attrs["gen_ai.usage.input_tokens"] = span.prompt_tokens
                if span.completion_tokens is not None:
                    attrs["gen_ai.usage.output_tokens"] = span.completion_tokens
                if span.total_tokens is not None:
                    attrs["gen_ai.usage.total_tokens"] = span.total_tokens

                # Cost
                if span.cost_usd is not None:
                    attrs["runport.cost_usd"] = span.cost_usd
                if span.cost_basis is not None:
                    attrs["runport.cost_basis"] = span.cost_basis

                # Events
                events_list: List[Dict[str, Any]] = []
                for ev in span.events:
                    events_list.append(
                        {
                            "timeUnixNano": datetime_to_unix_nano(ev.timestamp),
                            "name": ev.name,
                            "attributes": encode_otlp_attributes(ev.attributes),
                        }
                    )

                # Status
                if span.status == SpanStatus.OK:
                    status_dict = {"code": 1, "message": ""}
                elif span.status == SpanStatus.ERROR:
                    status_dict = {"code": 2, "message": span.error or "Error"}
                else:
                    status_dict = {"code": 0, "message": ""}

                # OTel Span Kind (1=INTERNAL, 3=CLIENT for LLM/TOOL)
                otel_kind_int = 3 if span.kind in (SpanKind.LLM, SpanKind.TOOL) else 1

                otlp_spans.append(
                    {
                        "traceId": trace_hex,
                        "spanId": span_hex,
                        "parentSpanId": parent_hex or "",
                        "name": span.name,
                        "kind": otel_kind_int,
                        "startTimeUnixNano": datetime_to_unix_nano(span.start_time) or "0",
                        "endTimeUnixNano": datetime_to_unix_nano(span.end_time) or "0",
                        "attributes": encode_otlp_attributes(attrs),
                        "events": events_list,
                        "status": status_dict,
                    }
                )

            resource_spans.append(
                {
                    "resource": {
                        "attributes": encode_otlp_attributes(res_attrs),
                    },
                    "scopeSpans": [
                        {
                            "scope": {
                                "name": "runport.tracer",
                                "version": "0.2.0",
                            },
                            "spans": otlp_spans,
                        }
                    ],
                }
            )

        return {"resourceSpans": resource_spans}

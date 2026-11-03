"""Hand-written test fixtures for the observability tests. Everything here is a TEST fixture; src never imports it."""

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from runport.classification.records import PredictionRecord
from runport.models.registry import Protocol
from runport.observability.events import RequestEvent

T0 = datetime(2026, 10, 15, 12, 0, 0, tzinfo=timezone.utc)
LABELS = ["QUERY", "GREETING", "CLOSING", "OTHER"]


def ts(seconds: float) -> str:
    return (T0 + timedelta(seconds=seconds)).isoformat()


def epoch(seconds: float) -> float:
    return (T0 + timedelta(seconds=seconds)).timestamp()


def started(rid, t, model="m1", run="r1", case="C1", **kw):
    return RequestEvent(kind="REQUEST_STARTED", request_id=rid, run_id=run, case_id=case, model_key=model, ts=ts(t), **kw)


def finished(rid, t, model="m1", run="r1", case="C1", status="OK", latency=100.0, p=50, c=10, basis="PROVIDER_REPORTED", actual="0.001", est=None, **kw):
    from decimal import Decimal
    return RequestEvent(
        kind="REQUEST_SUCCEEDED" if status != "ERROR" else "REQUEST_FAILED", request_id=rid, run_id=run, case_id=case, model_key=model, ts=ts(t),
        status=status, latency_ms=latency, prompt_tokens=p, completion_tokens=c, cost_basis=basis,
        actual_cost_usd=Decimal(actual) if actual is not None else None, estimated_cost_usd=Decimal(est) if est is not None else None, **kw)


def probs(label, top=0.9):
    rest = (1 - top) / (len(LABELS) - 1)
    return {l: (top if l == label else rest) for l in LABELS}


def intent_pred(case, label, model="custom-protocol-model", run="run1", top=None, status="OK", created="2026-10-15T12:00:00+00:00", dataset_version="test-ds", task="INTENT", **kw):
    dist = probs(label, top) if top is not None else None
    return PredictionRecord(
        record_id=f"{run}:{case}:{task}:{model}", run_id=run, case_id=case, task=task, model_key=model, protocol=Protocol.CHAT_COMPLETIONS,
        requested_model_id=model, prompt_version="sha256:test", dataset_version=dataset_version, status=status,
        predicted_label=label if status == "OK" else None, label_probs=dist,
        confidence_source="NATIVE_DISTRIBUTION" if dist else "NONE", created_at=created, **kw)


def lead_pred(case, yes_prob=None, need_cta=None, model="custom-protocol-model", run="lrun", status="OK", created="2026-10-15T12:00:00+00:00", task="LEAD", **kw):
    pred_label = "YES" if need_cta is True else ("NO" if need_cta is False else None)
    return PredictionRecord(
        record_id=f"{run}:{case}:{task}:{model}", run_id=run, case_id=case, task=task, model_key=model, protocol=Protocol.CHAT_COMPLETIONS,
        requested_model_id=model, prompt_version="sha256:test", dataset_version="test-ds", status=status, yes_prob=yes_prob,
        predicted_label=pred_label, created_at=created, **kw)


def write_preds(dirpath: Path, name: str, recs):
    dirpath.mkdir(parents=True, exist_ok=True)
    (dirpath / f"{name}.jsonl").write_text("\n".join(r.to_jsonl_row() for r in recs) + "\n", encoding="utf-8")



def write_labels(prep: Path, rows):
    d = prep / "annotations"
    d.mkdir(parents=True, exist_ok=True)
    (d / "approved_labels.jsonl").write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")


def label_row(case, task, expected, status="APPROVED", by="reviewer-a"):
    return {"case_id": case, "task": task, "expected": expected, "status": status, "approved_by": by, "approved_at": "2026-10-15T00:00:00+00:00"}


def make_prep(base: Path, version="prep-test"):
    """A minimal preparation folder: a manifest plus split/history metadata for two intent and two lead cases (no text)."""
    prep = base / version
    prep.mkdir(parents=True)
    (prep / "manifest.json").write_text(json.dumps({
        "prep_version": version, "parity_status": "PRODUCTION_PARITY_NOT_ESTABLISHED",
        "candidates": {"intent_2h": {"cases": 4}}, "session_comparison": {"sessions": {"2h": 2, "30m": 2}}}))
    return prep

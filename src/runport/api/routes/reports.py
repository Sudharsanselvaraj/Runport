"""Statistical evaluation reports and sanitized trace exports."""

from collections import Counter
import io
import json
import math
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import zipfile
from fastapi import APIRouter, HTTPException, Query, Response
from fastapi.responses import JSONResponse

from runport.core.config import settings
from runport.storage.db import DatabaseManager
from runport.providers.base import scrub_secrets

router = APIRouter(prefix="/reports", tags=["reports"])


def _pct(values: List[float], q: float) -> Optional[float]:
    """Pure-Python percentile calculation without external dependencies."""
    if not values:
        return None
    s = sorted(values)
    k = (len(s) - 1) * (q / 100.0)
    f = math.floor(k)
    c = math.ceil(k)
    if f == c:
        return s[int(k)]
    return s[f] * (c - k) + s[c] * (k - f)


def _wilson(k: int, n: int, z: float = 1.959964) -> Tuple[float, float]:
    """Wilson score confidence interval for a binomial proportion."""
    if n <= 0:
        return (0.0, 0.0)
    p = k / n
    d = 1.0 + (z * z) / n
    c = (p + (z * z) / (2.0 * n)) / d
    h = (z * math.sqrt(p * (1.0 - p) / n + (z * z) / (4.0 * n * n))) / d
    return (max(0.0, c - h), min(1.0, c + h))


def _cohen_kappa(a: List[str], b: List[str]) -> Optional[float]:
    """Cohen's Kappa agreement calculation."""
    n = len(a)
    if n == 0 or len(b) != n:
        return None
    po = sum(x == y for x, y in zip(a, b)) / n
    ca, cb = Counter(a), Counter(b)
    all_keys = set(ca.keys()) | set(cb.keys())
    pe = sum((ca[k] / n) * (cb[k] / n) for k in all_keys)
    if pe >= 1.0:
        return None
    return (po - pe) / (1.0 - pe)


def _prf(tp: int, fp: int, fn: int) -> Tuple[Optional[float], Optional[float], Optional[float]]:
    """Precision, recall, and F1 score."""
    p = tp / (tp + fp) if (tp + fp) > 0 else None
    r = tp / (tp + fn) if (tp + fn) > 0 else None
    if p is not None and r is not None and (p + r) > 0:
        f = 2.0 * p * r / (p + r)
    else:
        f = 0.0 if (tp + fp + fn) > 0 else None
    return p, r, f


@router.get("/export-traces")
def export_traces(
    format: str = Query("json", description="Export format: json or zip"),
) -> Response:
    """Exports sanitized traces with secrets and sensitive fields scrubbed."""
    settings.ensure_directories()
    events_file = settings.workspace_root / "data" / "traces" / "request_events.jsonl"

    traces = []
    if events_file.exists():
        with open(events_file, "r", encoding="utf-8") as f:
            for line in f:
                clean = line.strip()
                if clean:
                    try:
                        record = json.loads(clean)
                        scrubbed_record = json.loads(scrub_secrets(json.dumps(record)))
                        traces.append(scrubbed_record)
                    except Exception:
                        continue

    if format == "zip":
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("traces.jsonl", "\n".join(json.dumps(t) for t in traces))
            zf.writestr("manifest.json", json.dumps({"trace_count": len(traces), "sanitized": True}))
        buffer.seek(0)
        return Response(
            content=buffer.getvalue(),
            media_type="application/zip",
            headers={"Content-Disposition": "attachment; filename=runport_traces_sanitized.zip"},
        )

    return JSONResponse(
        content={
            "trace_count": len(traces),
            "sanitized": True,
            "traces": traces[:200],
        }
    )


@router.get("/{run_id}", response_model=Dict[str, Any])
def get_run_report(run_id: str) -> Dict[str, Any]:
    """Generates detailed statistical report with Wilson score CI, Kappa, and latency percentiles."""
    settings.ensure_directories()
    db = DatabaseManager(settings.db_path)
    db.init_db()

    run = db.get_evaluation_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail=f"Run '{run_id}' not found.")

    results = db.get_evaluation_results_for_run(run_id)
    if not results:
        return {
            "run_id": run_id,
            "total_cases": run.get("total_cases", 0),
            "completed_cases": 0,
            "failed_cases": 0,
            "message": "No individual result rows found for this run.",
        }

    # Latencies
    latencies = [float(r["latency_ms"]) for r in results if r.get("latency_ms") is not None]
    p50 = _pct(latencies, 50.0)
    p90 = _pct(latencies, 90.0)
    p95 = _pct(latencies, 95.0)
    p99 = _pct(latencies, 99.0)
    mean_lat = sum(latencies) / len(latencies) if latencies else None

    # Tokens
    p_tokens = [int(r["prompt_tokens"]) for r in results if r.get("prompt_tokens") is not None]
    c_tokens = [int(r["completion_tokens"]) for r in results if r.get("completion_tokens") is not None]
    mean_prompt_tokens = sum(p_tokens) / len(p_tokens) if p_tokens else None
    mean_comp_tokens = sum(c_tokens) / len(c_tokens) if c_tokens else None

    # Accuracy and Wilson CI
    accuracies = [float(r["accuracy"]) for r in results if r.get("accuracy") is not None]
    wilson_ci = None
    mean_acc = None
    if accuracies:
        k = sum(1 for a in accuracies if a >= 1.0)
        n = len(accuracies)
        mean_acc = k / n if n > 0 else 0.0
        ci_lo, ci_hi = _wilson(k, n)
        wilson_ci = [round(ci_lo, 4), round(ci_hi, 4)]

    # Confusion matrix and per-class metrics
    y_true = []
    y_pred = []
    for r in results:
        exp = str(r.get("expected_answer") or "").strip()
        out = str(r.get("generated_output") or "").strip()
        if exp:
            y_true.append(exp)
            y_pred.append(out)

    confusion_matrix_data = None
    kappa = None
    class_report = {}

    if y_true and len(y_true) == len(y_pred):
        unique_labels = sorted(list(set(y_true) | set(y_pred)))
        label_to_idx = {l: i for i, l in enumerate(unique_labels)}
        mat = [[0 for _ in unique_labels] for _ in unique_labels]
        for t, p in zip(y_true, y_pred):
            ti = label_to_idx.get(t)
            pi = label_to_idx.get(p)
            if ti is not None and pi is not None:
                mat[ti][pi] += 1

        confusion_matrix_data = {
            "labels": unique_labels,
            "matrix": mat,
        }

        # Cohen's Kappa
        k_val = _cohen_kappa(y_true, y_pred)
        if k_val is not None:
            kappa = round(float(k_val), 4)

        # Precision, Recall, F1 per class
        for i, l in enumerate(unique_labels):
            tp = mat[i][i]
            fp = sum(mat[r][i] for r in range(len(unique_labels)) if r != i)
            fn = sum(mat[i][c] for c in range(len(unique_labels)) if c != i)
            p_val, r_val, f_val = _prf(tp, fp, fn)
            class_report[l] = {
                "precision": round(p_val, 4) if p_val is not None else None,
                "recall": round(r_val, 4) if r_val is not None else None,
                "f1": round(f_val, 4) if f_val is not None else None,
                "support": tp + fn,
            }

    # Cost per 1k cases
    cost_str = run.get("total_cost_usd")
    cost_usd = float(cost_str) if cost_str is not None else 0.0
    cost_per_1k = (cost_usd / len(results) * 1000.0) if results else 0.0

    return {
        "run_id": run_id,
        "model_id": run.get("model_id"),
        "dataset_path": run.get("dataset_path"),
        "timestamp": run.get("timestamp"),
        "total_cases": len(results),
        "completed_cases": sum(1 for r in results if r.get("accuracy") is not None or r.get("generated_output")),
        "accuracy": round(mean_acc, 4) if mean_acc is not None else None,
        "wilson_ci": wilson_ci,
        "mean_latency_ms": round(mean_lat, 2) if mean_lat is not None else None,
        "latency_p50_ms": round(p50, 2) if p50 is not None else None,
        "latency_p90_ms": round(p90, 2) if p90 is not None else None,
        "latency_p95_ms": round(p95, 2) if p95 is not None else None,
        "latency_p99_ms": round(p99, 2) if p99 is not None else None,
        "mean_prompt_tokens": round(mean_prompt_tokens, 1) if mean_prompt_tokens is not None else None,
        "mean_completion_tokens": round(mean_comp_tokens, 1) if mean_comp_tokens is not None else None,
        "total_cost_usd": round(cost_usd, 6),
        "cost_per_1k_cases_usd": round(cost_per_1k, 4),
        "cohen_kappa": kappa,
        "confusion_matrix": confusion_matrix_data,
        "classification_report": class_report,
    }

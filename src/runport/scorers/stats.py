"""Statistical helpers and confidence metrics for benchmark scoring.

Denominators are always explicit; missing or invalid values remain NaN, never fabricated or imputed as zero.
"""

from __future__ import annotations

import hashlib
import math
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple
import numpy as np
import pandas as pd

SEED = 20261021
N_BOOT = 2000
NAN = float("nan")


def sha256_file(path: Path) -> str:
    """Computes SHA-256 hex digest of a file in 1MB chunks."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def rng_for(label: str, seed: int = SEED) -> np.random.Generator:
    """Deterministic random generator derived from seed and label."""
    digest = hashlib.sha256(f"{seed}|{label}".encode()).digest()
    return np.random.default_rng(int.from_bytes(digest[:8], "big"))


def wilson(k: int, n: int, z: float = 1.959964) -> Tuple[float, float]:
    """Wilson score confidence interval for a binomial proportion.
    
    Returns (lo, hi) clamped to [0.0, 1.0]. Returns (NaN, NaN) if n <= 0.
    """
    if n <= 0:
        return (float("nan"), float("nan"))
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (max(0.0, c - h), min(1.0, c + h))


def boot_ci(values: np.ndarray, stat, label: str, n_boot: int = N_BOOT, seed: int = SEED) -> Tuple[float, float]:
    """Bootstrap 95% confidence interval for a summary statistic."""
    v = np.asarray(values, dtype=float)
    v = v[~np.isnan(v)]
    if len(v) < 2:
        return (float("nan"), float("nan"))
    g = rng_for(label, seed)
    idx = g.integers(0, len(v), size=(n_boot, len(v)))
    s = np.array([stat(v[i]) for i in idx])
    return (float(np.percentile(s, 2.5)), float(np.percentile(s, 97.5)))


def pct(v: np.ndarray, q: float) -> float:
    """Nearest-rank percentile for an array, ignoring NaNs."""
    v = np.asarray(v, dtype=float)
    v = v[~np.isnan(v)]
    return float(np.percentile(v, q)) if len(v) else float("nan")


def holm(pvals: List[float]) -> List[float]:
    """Holm-Bonferroni step-down adjustment for multiple hypothesis testing."""
    order = sorted(range(len(pvals)), key=lambda i: pvals[i])
    adj = [0.0] * len(pvals)
    running = 0.0
    m = len(pvals)
    for rank, i in enumerate(order):
        running = max(running, min(1.0, (m - rank) * pvals[i]))
        adj[i] = running
    return adj


def cohen_kappa(a: List[str], b: List[str]) -> float:
    """Computes Cohen's Kappa for inter-rater or inter-model agreement."""
    n = len(a)
    if n == 0 or len(b) != n:
        return float("nan")
    po = sum(x == y for x, y in zip(a, b)) / n
    ca, cb = pd.Series(a).value_counts(), pd.Series(b).value_counts()
    pe = sum((ca.get(k, 0) / n) * (cb.get(k, 0) / n) for k in set(ca.index) | set(cb.index))
    return float("nan") if pe == 1 else (po - pe) / (1 - pe)


def prf(tp: int, fp: int, fn: int) -> Tuple[float, float, float]:
    """Precision, recall, and F1 with explicit zero/NaN handling."""
    p = tp / (tp + fp) if (tp + fp) else NAN
    r = tp / (tp + fn) if (tp + fn) else NAN
    f = 2 * p * r / (p + r) if (p == p and r == r and (p + r) > 0) else (NAN if not (tp + fp + fn) else 0.0)
    return p, r, f

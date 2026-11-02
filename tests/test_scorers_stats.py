"""Unit tests for statistical helpers in runport.scorers.stats."""

import numpy as np
import pytest

from runport.scorers.stats import (
    boot_ci,
    cohen_kappa,
    holm,
    wilson,
)


def test_wilson_score_interval():
    # Extreme cases
    lo0, hi0 = wilson(0, 10)
    assert lo0 == 0.0
    assert 0.0 < hi0 < 0.35

    lo_full, hi_full = wilson(10, 10)
    assert 0.65 < lo_full < 1.0
    assert pytest.approx(hi_full, rel=1e-9) == 1.0

    # Symmetric case
    lo5, hi5 = wilson(5, 10)
    assert 0.23 < lo5 < 0.25
    assert 0.75 < hi5 < 0.77

    # Empty sample returns NaNs
    lo_nan, hi_nan = wilson(0, 0)
    assert np.isnan(lo_nan) and np.isnan(hi_nan)


def test_holm_bonferroni_adjustment():
    # Empty
    assert holm([]) == []

    # Single p-value unchanged
    assert holm([0.05]) == [0.05]

    # Monotonicity and bounding preserved
    raw = [0.01, 0.04, 0.03, 0.005]
    adj = holm(raw)
    assert len(adj) == 4
    # Lowest raw p-value (0.005) multiplied by 4 -> 0.02
    assert pytest.approx(adj[3], rel=1e-5) == 0.02
    for a in adj:
        assert 0.0 <= a <= 1.0


def test_boot_ci_reproducibility():
    data = np.array([1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0])
    stat = np.mean
    lo1, hi1 = boot_ci(data, stat, label="test_seed", seed=42)
    lo2, hi2 = boot_ci(data, stat, label="test_seed", seed=42)
    assert lo1 == lo2
    assert hi1 == hi2
    assert lo1 < np.mean(data) < hi1


def test_cohen_kappa():
    # Perfect agreement
    a = ["A", "B", "A", "C"]
    assert cohen_kappa(a, a) == 1.0

    # Intermediate agreement
    rater_a = ["A", "B", "A", "C", "B", "A", "C", "C", "B", "A"]
    rater_b = ["A", "B", "C", "C", "B", "A", "C", "B", "B", "A"]
    k = cohen_kappa(rater_a, rater_b)
    assert 0.0 < k < 1.0

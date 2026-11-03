# Statistical & Operational Metrics Reference

This document provides mathematical definitions, formulas, and denominators for every statistical, operational, and financial metric computed by Runport.

---

## 1. Core Invariants

1. **Null is not 0**: Missing tokens, latency, confidence, or cost remain `None` / `UNAVAILABLE`. Never fabricate or default missing telemetry to zero.
2. **Supervised Metrics Require Human Ground Truth**: Supervised accuracy, F1, and calibration are computed strictly against human-approved annotations. Model consensus or agreement is never presented as accuracy.
3. **Explicit Denominators**: Denominators always account for the total sample size ($N_{\text{total}}$). Invalid, timed-out, or malformed outputs are recorded as errors in the denominator rather than silently discarded.

---

## 2. Supervised Quality Metrics

### 2.1 Multiclass & Binary Accuracy

$$\text{Accuracy} = \frac{N_{\text{correct}}}{N_{\text{total}}}$$

- **Numerator ($N_{\text{correct}}$)**: Number of cases where the validated model prediction matches the ground truth label.
- **Denominator ($N_{\text{total}}$)**: Total evaluation cases in the split. Invalid outputs, errors, and unparsable responses count in the denominator as incorrect ($0$).

---

### 2.2 Per-Class Precision, Recall, and F1

For each target class $c \in C$:

- **True Positives ($\text{TP}_c$)**: Reference is $c$ and prediction is $c$.
- **False Positives ($\text{FP}_c$)**: Reference is not $c$ but prediction is $c$.
- **False Negatives ($\text{FN}_c$)**: Reference is $c$ but prediction is not $c$ (including invalid output).

$$\text{Precision}_c = \frac{\text{TP}_c}{\text{TP}_c + \text{FP}_c}$$

$$\text{Recall}_c = \frac{\text{TP}_c}{\text{TP}_c + \text{FN}_c}$$

$$F1_c = \frac{2 \cdot \text{Precision}_c \cdot \text{Recall}_c}{\text{Precision}_c + \text{Recall}_c}$$

---

### 2.3 Wilson Score Confidence Interval

For binomial proportions (e.g. accuracy or validity rate), Runport computes the asymmetric two-sided 95% Wilson score interval:

$$w = \frac{\hat{p} + \frac{z^2}{2n} \pm z \sqrt{\frac{\hat{p}(1 - \hat{p})}{n} + \frac{z^2}{4n^2}}}{1 + \frac{z^2}{n}}$$

Where:
- $\hat{p} = \frac{k}{n}$ (observed proportion)
- $n = N_{\text{total}}$
- $z = 1.95996$ (for 95% two-sided confidence)

---

### 2.4 Bootstrap Confidence Intervals

For continuous summary statistics (such as mean latency or aggregate cost), Runport computes 95% bootstrap confidence intervals with $B = 2,000$ resamples and deterministic pseudo-random seeds:

$$\text{CI}_{95\%} = \left[ q_{2.5\%}(S^*), q_{97.5\%}(S^*) \right]$$

---

### 2.5 Inter-Rater / Inter-Model Agreement (Cohen's Kappa)

Cohen's $\kappa$ measures chance-corrected agreement between two models or between a candidate model and an unverified reference:

$$\kappa = \frac{p_o - p_e}{1 - p_e}$$

Where:
- $p_o$: Observed agreement proportion
- $p_e$: Expected agreement proportion under statistical independence

> [!NOTE]
> Agreement is reported exclusively as $\kappa$. It is never labeled as accuracy unless compared directly to human ground truth.

---

## 3. Operational & Latency Metrics

### 3.1 Mean & Percentile Latency (p50, p90, p95, p99)

- **Mean Latency**: Arithmetic mean across successful invocations.
- **Rank Percentiles**: Calculated via nearest-rank interpolation over non-null valid response times:
  $$\text{Rank} = \frac{P}{100} \cdot (N - 1)$$

---

## 4. Spend & Financial Accounting

- **`ACTUAL`**: Exact USD cost reported directly by upstream provider billing headers.
- **`ESTIMATED`**: Computed via verified catalog token rates:
  $$\text{Cost} = \left(\frac{\text{Tokens}_{\text{in}}}{10^6} \cdot \text{Rate}_{\text{in}}\right) + \left(\frac{\text{Tokens}_{\text{out}}}{10^6} \cdot \text{Rate}_{\text{out}}\right)$$
- **`UNRESOLVED`**: Live request completed without cost or token telemetry. Halts subsequent live runs fail-closed until reconciled.
- **`UNAVAILABLE`**: Zero-cost / deterministic replay execution ($0.00 USD).

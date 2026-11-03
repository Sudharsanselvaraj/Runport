# Runport Evaluation Metrics Specification

This document provides mathematical definitions, computational procedures, and explicit denominators for every statistical, operational, and financial metric computed by Runport.

---

## 1. Core Evaluation Invariants

1. **Null is not 0**: Missing tokens, latency, confidence, or cost remain `None` / `UNAVAILABLE`. Missing telemetry is never fabricated or coerced to zero.
2. **Supervised Metrics Require Human Ground Truth**: Supervised accuracy, F1, and calibration are computed strictly against human-approved annotations (`is_verified=True` / ground-truth references). Model consensus or agreement is never presented as accuracy.
3. **Strict Denominators**: Denominators always account for the total sample size ($N_{\text{total}}$), explicitly recording invalid, timed-out, or malformed outputs rather than discarding them.

---

## 2. Supervised Quality Metrics

### 2.1 Multiclass & Binary Accuracy

$$\text{Accuracy} = \frac{N_{\text{correct}}}{N_{\text{total}}}$$

- **Numerator ($N_{\text{correct}}$)**: Number of cases where the validated model prediction matches the ground truth label exactly.
- **Denominator ($N_{\text{total}}$)**: Total number of evaluation cases in the split. Invalid outputs, errors, and unparsable responses count in the denominator as incorrect ($0$).
- **Provenance**: Computed only when verified ground truth references exist.

### 2.2 Per-Class Precision, Recall, and F1

For each target class $c \in C$:

- **True Positives ($\text{TP}_c$)**: Reference is $c$ and prediction is $c$.
- **False Positives ($\text{FP}_c$)**: Reference is not $c$ but prediction is $c$.
- **False Negatives ($\text{FN}_c$)**: Reference is $c$ but prediction is not $c$ (including invalid output).

$$\text{Precision}_c = \frac{\text{TP}_c}{\text{TP}_c + \text{FP}_c}$$
$$\text{Recall}_c = \frac{\text{TP}_c}{\text{TP}_c + \text{FN}_c}$$
$$F1_c = \frac{2 \cdot \text{Precision}_c \cdot \text{Recall}_c}{\text{Precision}_c + \text{Recall}_c}$$

- **Zero Division**: When $(\text{TP}_c + \text{FP}_c) = 0$ or $(\text{TP}_c + \text{FN}_c) = 0$, the metric is defined as $0.0000$ with support recorded as $0$.

### 2.3 Macro-Averaged F1

$$\text{Macro } F1 = \frac{1}{|C|} \sum_{c \in C} F1_c$$

- **Denominator ($|C|$)**: Total number of target classes in the task specification with non-zero reference support.

### 2.4 Brier Calibration Score

$$\text{Brier Score} = \frac{1}{N_{\text{scored}}} \sum_{i=1}^{N_{\text{scored}}} (p_i - y_i)^2$$

- **$p_i$**: Model-reported probability for positive class ($p \in [0.0, 1.0]$).
- **$y_i$**: Ground truth indicator ($1$ for positive, $0$ for negative).
- **Denominator ($N_{\text{scored}}$)**: Number of cases with explicit probability telemetry. If missing, Brier score remains `None`.

### 2.5 Wilson Binomial Confidence Interval

Calculates the two-sided asymmetric 95% score interval for observed success proportion $\hat{p} = k / n$:

$$w = \frac{\hat{p} + \frac{z^2}{2n} \pm z \sqrt{\frac{\hat{p}(1 - \hat{p})}{n} + \frac{z^2}{4n^2}}}{1 + \frac{z^2}{n}}$$

- $z = 1.95996$ (for 95% confidence).
- $n = N_{\text{total}}$ (denominator).

---

## 3. Operational & System Metrics

### 3.1 Mean & Percentile Latency (p50, p90, p95, p99)

$$\text{Mean Latency} = \frac{1}{N_{\text{valid\_latency}}} \sum_{i=1}^{N_{\text{valid\_latency}}} \text{latency\_ms}_i$$

- **Percentiles**: Computed via linear rank interpolation on sorted valid latency measurements:
  $$\text{Rank} = \frac{P}{100} \cdot (N - 1)$$
- **Denominator**: Only executions that successfully completed transport without timeout or local socket drop. Missing latencies remain `None`.

### 3.2 Output Validity Rate

$$\text{Validity Rate} = \frac{N_{\text{valid}}}{N_{\text{total}}}$$

- **Numerator ($N_{\text{valid}}$)**: Cases where output successfully passed strict schema and label validators.
- **Denominator ($N_{\text{total}}$)**: All planned cases.

---

## 4. Financial & Spend Metrics

### 4.1 Actual vs. Estimated Spend

- **Actual Spend (`ACTUAL`)**: Exact USD cost reported directly by upstream provider usage headers or billing payload.
- **Estimated Spend (`ESTIMATED`)**: Computed using verified catalog rates:
  $$\text{Cost} = \left(\frac{\text{Tokens}_{\text{in}}}{10^6} \cdot \text{Rate}_{\text{in}}\right) + \left(\frac{\text{Tokens}_{\text{out}}}{10^6} \cdot \text{Rate}_{\text{out}}\right)$$
- **Unresolved Spend (`UNRESOLVED`)**: Live request completed but cost/tokens were missing. Booked at `$0.00` and halts subsequent live runs fail-closed until reconciled.
- **Unavailable (`UNAVAILABLE`)**: Local / deterministic replay execution ($0.00 USD).

### 4.2 Cost per 1,000 Inferences (Cost/1k)

$$\text{Cost per 1k} = \left(\frac{\text{Total Spend USD}}{N_{\text{total}}}\right) \times 1000$$

- **Denominator ($N_{\text{total}}$)**: Number of evaluation cases in the run.
- If total spend is unpriced or `UNAVAILABLE`, Cost per 1k remains `None`.

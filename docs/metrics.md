# Statistical & Operational Metrics Reference

This document provides mathematical definitions, formulas, sample denominators, and implementation details for every metric computed by Runport.

---

## 1. Core Evaluation Invariants

1. **Null is Not 0**: Missing tokens, latency, confidence, or cost remain `None` / `UNAVAILABLE`. Never fabricate or default missing telemetry to zero.
2. **Supervised Metrics Require Human Ground Truth**: Supervised accuracy, F1, and calibration are computed strictly against human-approved annotations. Model consensus or agreement is never presented as accuracy.
3. **Explicit Denominators**: Denominators always account for the total sample size ($N_{\text{total}}$). Invalid, timed-out, or malformed outputs are recorded as errors in the denominator rather than silently discarded.
4. **No Tuning on Held-Out Splits**: Decision thresholds and hyper-parameters are calibrated on DEV only, frozen, and evaluated unchanged on TEST.

---

## 2. Supervised Quality Metrics

### 2.1 Multiclass & Binary Accuracy

$$\text{Accuracy} = \frac{N_{\text{correct}}}{N_{\text{total}}}$$

- **Numerator ($N_{\text{correct}}$)**: Number of cases where the validated model prediction matches the ground truth label.
- **Denominator ($N_{\text{total}}$)**: Total evaluation cases in the split. Invalid outputs, errors, and unparsable responses count in the denominator as incorrect ($0$).

```python
from runport.scorers.classification import ClassificationReportScorer

scorer = ClassificationReportScorer(allowed_labels=["QUERY", "GREETING", "CLOSING", "OTHER"])
report = scorer.compute_report(predictions, ground_truth)
print(f"Accuracy: {report.accuracy:.2%}")
```

---

### 2.2 Per-Class Precision, Recall, and F1

For each target class $c \in C$:

- **True Positives ($\text{TP}_c$)**: Reference is $c$ and prediction is $c$.
- **False Positives ($\text{FP}_c$)**: Reference is not $c$ but prediction is $c$.
- **False Negatives ($\text{FN}_c$)**: Reference is $c$ but prediction is not $c$ (including invalid or malformed output).

$$\text{Precision}_c = \frac{\text{TP}_c}{\text{TP}_c + \text{FP}_c}$$

$$\text{Recall}_c = \frac{\text{TP}_c}{\text{TP}_c + \text{FN}_c}$$

$$F1_c = \frac{2 \cdot \text{Precision}_c \cdot \text{Recall}_c}{\text{Precision}_c + \text{Recall}_c}$$

$$\text{Macro-F1} = \frac{1}{|C|} \sum_{c \in C} F1_c$$

> [!NOTE]
> If $\text{TP}_c + \text{FP}_c = 0$, precision is defined as `NaN` (or $0.0$ when penalizing unpredicted classes); Runport never fabricates an arbitrary score.

---

### 2.3 Wilson Score Confidence Interval

For binomial proportions (such as accuracy or validity rate), Runport computes the asymmetric two-sided 95% Wilson score interval:

$$w = \frac{\hat{p} + \frac{z^2}{2n} \pm z \sqrt{\frac{\hat{p}(1 - \hat{p})}{n} + \frac{z^2}{4n^2}}}{1 + \frac{z^2}{n}}$$

Where:
- $\hat{p} = \frac{k}{n}$ (observed proportion of correct cases)
- $n = N_{\text{total}}$
- $z = 1.95996$ (for 95% two-sided confidence)

Unlike the standard Wald normal approximation ($\hat{p} \pm z\sqrt{\hat{p}(1-\hat{p})/n}$), the Wilson score interval provides robust coverage even when $n$ is small or $\hat{p}$ is close to $0$ or $1$.

```python
from runport.scorers.stats import wilson

lo, hi = wilson(k=85, n=100)
print(f"95% CI: [{lo:.3f}, {hi:.3f}]")  # [0.767, 0.907]
```

---

### 2.4 Non-Parametric Bootstrap Confidence Intervals

For continuous summary statistics (such as mean latency or aggregate cost), Runport computes 95% bootstrap confidence intervals with $B = 2,000$ resamples and deterministic pseudo-random seeds:

$$\text{CI}_{95\%} = \left[ q_{2.5\%}(S^*), q_{97.5\%}(S^*) \right]$$

```python
import numpy as np
from runport.scorers.stats import boot_ci

latencies = np.array([120.5, 145.2, 98.1, 310.4, 115.0])
ci_lo, ci_hi = boot_ci(latencies, stat=np.mean, label="latency_boot")
print(f"Mean Latency 95% CI: [{ci_lo:.1f}ms, {ci_hi:.1f}ms]")
```

---

### 2.5 Inter-Rater / Inter-Model Agreement (Cohen's Kappa)

Cohen's $\kappa$ measures chance-corrected agreement between two models or between a candidate model and an unverified baseline:

$$\kappa = \frac{p_o - p_e}{1 - p_e}$$

Where:
- $p_o$: Observed agreement proportion ($\sum_i p_{ii}$)
- $p_e$: Expected agreement proportion under statistical independence ($\sum_i p_{i\cdot} p_{\cdot i}$)

| $\kappa$ Range | Interpretation |
|:---|:---|
| $< 0.00$ | Poor (Less than chance agreement) |
| $0.00 - 0.20$ | Slight agreement |
| $0.21 - 0.40$ | Fair agreement |
| $0.41 - 0.60$ | Moderate agreement |
| $0.61 - 0.80$ | Substantial agreement |
| $0.81 - 1.00$ | Almost perfect agreement |

> [!IMPORTANT]
> Model agreement is reported strictly as $\kappa$. It is never labeled as accuracy unless compared directly to human ground truth.

---

### 2.6 Multiple Comparisons (Holm-Bonferroni Step-Down)

When evaluating multiple candidate models against a baseline, Runport applies the Holm-Bonferroni method to control the Family-Wise Error Rate (FWER) without sacrificing power:

1. Sort $M$ p-values in ascending order: $p_{(1)} \le p_{(2)} \le \dots \le p_{(M)}$.
2. For each rank $k \in \{1, \dots, M\}$, adjust:
   $$p_{(k)}^{\text{adj}} = \min\left(1, \max_{j \le k} \left\{ (M - j + 1) \cdot p_{(j)} \right\}\right)$$

```python
from runport.scorers.stats import holm

raw_pvals = [0.004, 0.021, 0.045, 0.120]
adjusted = holm(raw_pvals)
```

---

## 3. RAG & Retrieval Metrics

Runport evaluates Retrieval-Augmented Generation (RAG) pipelines across decoupled retrieval, generation, and grounding dimensions:

| Metric | Focus | Description |
|:---|:---|:---|
| **Contextual Faithfulness** | Generation | Evaluates whether every claim in the response is supported by the retrieved context. |
| **Answer Relevancy** | Generation | Evaluates how directly the answer addresses the original query without extraneous details. |
| **Contextual Recall** | Retrieval | Evaluates whether the retrieved context contains all necessary ground-truth facts. |
| **Contextual Precision** | Retrieval | Measures if relevant knowledge chunks are ranked higher than irrelevant ones. |
| **Groundedness Score** | End-to-End | Composite ratio of verified cited statements to total statements in output. |

---

## 4. Operational & Latency Metrics

### 4.1 Mean & Percentile Latency ($p_{50}, p_{90}, p_{95}, p_{99}$)

- **Mean Latency**: Arithmetic mean across successful invocations.
- **Percentiles**: Calculated via nearest-rank interpolation over non-null valid response times:
  $$\text{Rank} = \frac{P}{100} \cdot (N - 1)$$

### 4.2 Token Consumption
- **Input Tokens ($\text{Tokens}_{\text{in}}$)**: Prompt tokens reported by provider.
- **Output Tokens ($\text{Tokens}_{\text{out}}$)**: Completion tokens reported by provider.
- If tokens are missing from provider telemetry, they remain `None` and are not defaulted to zero.

---

## 5. Spend & Financial Accounting

Every transaction is committed to the append-only SQLite WAL ledger with an explicit provenance tag:

- **`ACTUAL`**: Exact USD cost reported directly in provider HTTP response headers or metadata.
- **`ESTIMATED`**: Computed via verified catalog token rates:
  $$\text{Cost} = \left(\frac{\text{Tokens}_{\text{in}}}{10^6} \cdot \text{Rate}_{\text{in}}\right) + \left(\frac{\text{Tokens}_{\text{out}}}{10^6} \cdot \text{Rate}_{\text{out}}\right)$$
- **`UNRESOLVED`**: Live request completed without cost or token telemetry. Halts subsequent live runs fail-closed until reconciled.
- **`UNAVAILABLE`**: Zero-cost / deterministic local execution ($0.00 USD) such as Ollama, Python callables, or offline replays.
- **`REPLAYED`**: Offline re-execution from recorded fixtures ($0.00 USD).

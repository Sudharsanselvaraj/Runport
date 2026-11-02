# Ground-Truth Annotation & Evaluation (`runport annotate`)

Runport requires human-approved ground-truth labels for all supervised metrics (Accuracy, F1, Calibration). Unanimous model agreement is never presented as ground truth.

---

## 1. Ground-Truth Workflow

```bash
# Check status of annotations for a prepared dataset
uv run runport annotate status --prep-dir data/evaluation/

# Queue cases for independent blind annotation
uv run runport annotate queue --prep-dir data/evaluation/ --annotator-id rater-1

# Adjudicate discrepancies between independent annotators
uv run runport annotate adjudicate --prep-dir data/evaluation/

# Approve adjudicated ground-truth labels with named human authorization
uv run runport annotate approve --prep-dir data/evaluation/ --approver-name "Lead Evaluator"

# Cryptographically freeze approved ground truth for benchmark reporting
uv run runport annotate freeze --prep-dir data/evaluation/
```

---

## 2. Invariants & Rules

1. **Two-Pass Annotation & Adjudication**: Cases are evaluated by independent raters; conflicting labels must be explicitly adjudicated before approval.
2. **Named Human Approval**: Metrics remain `GROUND TRUTH PENDING` until an authorized human signs off (`approved_by`).
3. **Never Tune on Held-Out Test Split**: Thresholds are computed exclusively on `DEV`, frozen, and evaluated without alteration on `TEST`.
4. **Append-Only & Immutable**: Once frozen, ground truth cannot be modified in place.

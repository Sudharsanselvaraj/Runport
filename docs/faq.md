# Frequently Asked Questions (FAQ)

Honest, practical answers to common questions about Runport.

---

### How does Runport prevent runaway spending?
Runport uses an append-only SQLite WAL ledger and checks four distinct spend ceilings (total budget, pilot cap, per-run limit, and per-case limit) before every single request. If any ceiling would be exceeded, execution halts fail-closed before the network socket opens.

---

### Can I benchmark private endpoints or local models without internet?
Yes. Runport supports local targets including `ollama`, in-process `python_target` callables, deterministic `--replay`, and custom internal `http_workflow` endpoints. Runport requires zero internet connectivity for local and replay benchmarks.

---

### Why does Runport reject model-to-model agreement as accuracy?
Two models can agree on an answer and both be completely wrong. Agreement (measured by Cohen's $\kappa$ or consensus percent) is inter-rater reliability, not accuracy. Supervised metrics (accuracy, F1, calibration) are computed strictly against human-verified annotations.

---

### What does `UNRESOLVED` spend mean and why does it block my next run?
If a live provider returns a valid response but omits token usage or billing metadata, Runport cannot verify how much you were charged. To prevent silent debt accumulation, Runport books the transaction as `UNRESOLVED` ($0.00 initial charge) and halts subsequent live runs fail-closed until an operator reconciles the actual cost via `runport budget reconcile`.

---

### Does Runport send telemetry or analytics back to anyone?
No. Runport has zero phone-home mechanisms, zero remote telemetry, and zero tracking pixels. Everything runs locally on your machine.

---

### How do I integrate Runport into CI/CD pipelines?
Use deterministic replay (`--replay`) or local targets in your CI test matrix. Because replay executions book `$0.00` spend and run completely offline without API credentials, they are safe to run on pull requests and automated build agents.

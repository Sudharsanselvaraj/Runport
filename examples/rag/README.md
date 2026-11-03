# Decoupled RAG Benchmark Example

This example demonstrates decoupled retrieval evaluation against a synthetic knowledge base.

---

## Files
- `documents.jsonl`: Knowledge base corpus items.
- `eval.jsonl`: Questions with ground truth reference documents.
- `run.py`: Decoupled retrieval scorer computing Recall@1.

---

## How to Run

```bash
uv run python examples/rag/run.py
```

Runs completely offline in `<0.1s`.

#!/usr/bin/env python3
"""Decoupled RAG retrieval and answer evaluation example."""

import json
from pathlib import Path


def simple_retrieve(query: str, docs: list) -> str:
    words = set(query.lower().split())
    best_doc = None
    best_overlap = -1
    for doc in docs:
        doc_words = set(doc["content"].lower().split())
        overlap = len(words & doc_words)
        if overlap > best_overlap:
            best_overlap = overlap
            best_doc = doc
    return best_doc["doc_id"] if best_doc else ""


def main():
    base_dir = Path(__file__).parent
    docs = [json.loads(line) for line in (base_dir / "documents.jsonl").read_text().splitlines() if line.strip()]
    eval_cases = [json.loads(line) for line in (base_dir / "eval.jsonl").read_text().splitlines() if line.strip()]

    hit_count = 0
    for case in eval_cases:
        retrieved_id = simple_retrieve(case["query"], docs)
        hit = retrieved_id == case["expected_doc"]
        if hit:
            hit_count += 1
        print(f"Query: {case['query'][:35]}... -> Retrieved: {retrieved_id} (Hit: {hit})")

    retrieval_recall = hit_count / len(eval_cases)
    print(f"\nRetrieval Recall@1: {retrieval_recall:.2%}")


if __name__ == "__main__":
    main()

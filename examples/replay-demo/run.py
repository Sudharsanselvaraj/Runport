#!/usr/bin/env python3
"""Deterministic replay benchmark demonstration. Books $0.00 spend offline."""

from decimal import Decimal
from pathlib import Path
from runport.runs.replay import ReplayRunner


def main():
    fixtures_file = Path(__file__).parent / "fixtures.jsonl"
    runner = ReplayRunner(fixtures=fixtures_file, target_id="mock-replay-model")

    cases = [
        {"id": "rep-001", "query": "What is the capital of France?"},
        {"id": "rep-002", "query": "Convert 100 EUR to USD"},
        {"id": "rep-003", "query": "Explain quantum entanglement briefly"},
    ]

    total_cost = Decimal("0.00")
    for case in cases:
        res = runner.replay_case(case["id"], case)
        total_cost += res.cost_usd
        print(f"[{res.provenance}] {case['query'][:30]}... -> '{res.output_text}' (Cost: ${res.cost_usd})")
        assert res.provenance == "REPLAYED"
        assert res.cost_usd == Decimal("0.0000")

    print(f"\nReplay execution finished. Total booked spend: ${total_cost:.2f} (Guaranteed $0.00)")


if __name__ == "__main__":
    main()

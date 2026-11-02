"""Unit tests for the Runport replay subsystem."""

from decimal import Decimal
import json
import pytest

from runport.runs.replay import ReplayRunner, ReplayTarget
from runport.targets import CostBasis, TargetStatus


def test_replay_runner_in_memory():
    fixtures = [
        {
            "case_id": "c1",
            "output_text": "Answer 1",
            "latency_ms": 125.5,
            "tokens_in": 12,
            "tokens_out": 4,
            "cost_usd": "0.0015",  # original recorded cost
        },
        {
            "case_id": "c2",
            "output_text": "Answer 2",
            "latency_ms": 95.0,
        },
    ]

    runner = ReplayRunner(fixtures=fixtures, target_id="model-replay")

    # Case 1
    res1 = runner.replay_case("c1")
    assert res1.is_success is True
    assert res1.output_text == "Answer 1"
    assert res1.is_replay is True
    assert res1.provenance == "REPLAYED"
    # Invariant: Replay cost is ALWAYS zero / not booked to live budget
    assert res1.cost_usd == Decimal("0.0000")
    assert res1.cost_basis == CostBasis.UNAVAILABLE
    assert res1.tokens_in == 12
    assert res1.tokens_out == 4
    assert res1.latency_ms == 125.5
    assert res1.metadata["original_cost_usd"] == "0.0015"

    # Case 2
    res2 = runner.replay_case("c2")
    assert res2.is_success is True
    assert res2.output_text == "Answer 2"
    assert res2.is_replay is True
    assert res2.provenance == "REPLAYED"
    assert res2.cost_usd == Decimal("0.0000")

    # Missing Case
    res_missing = runner.replay_case("c_unknown")
    assert res_missing.is_success is False
    assert res_missing.status == TargetStatus.FAILED
    assert res_missing.is_replay is True
    assert res_missing.provenance == "REPLAYED"
    assert "No recorded replay fixture found" in str(res_missing.error_message)


def test_replay_runner_jsonl(tmp_path):
    jsonl_file = tmp_path / "fixtures.jsonl"
    lines = [
        json.dumps({"case_id": "item_1", "query": "hello", "output_text": "world"}),
        json.dumps({"case_id": "item_2", "query": "ping", "output_text": "pong"}),
    ]
    jsonl_file.write_text("\n".join(lines), encoding="utf-8")

    runner = ReplayRunner(fixtures=jsonl_file, target_id="jsonl-replay")
    results = runner.replay_dataset([{"case_id": "item_1"}, {"case_id": "item_2"}])

    assert len(results) == 2
    assert results[0].output_text == "world"
    assert results[1].output_text == "pong"
    for r in results:
        assert r.is_replay is True
        assert r.provenance == "REPLAYED"
        assert r.cost_usd == Decimal("0.0000")


def test_replay_target_abstraction():
    fixtures = [
        {"case_id": "tc-100", "output": "Unified target output"},
    ]
    target = ReplayTarget(
        target_id="target-replay-mock",
        name="Mock Replay Target",
        fixtures=fixtures,
    )

    res = target.execute({"query": "run"}, context={"case_id": "tc-100"})
    assert res.is_success is True
    assert res.output_text == "Unified target output"
    assert res.is_replay is True
    assert res.provenance == "REPLAYED"
    assert res.cost_usd == Decimal("0.0000")


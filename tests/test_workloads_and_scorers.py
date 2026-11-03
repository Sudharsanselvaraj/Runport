"""Unit tests for Phase D: Workloads, scorers, LLM judge, and report generation."""

from decimal import Decimal
import json
from pathlib import Path
import pytest

from runport.reports.generator import ReportGenerator, RunManifest, generate_caveats
from runport.scorers.classification import AccuracyScorer, BrierScoreScorer
from runport.scorers.extraction import FieldMatchScorer, JSONSchemaScorer
from runport.scorers.generation import KeywordContainmentScorer, TokenOverlapScorer
from runport.scorers.llm_judge import LLMJudgeScorer
from runport.workloads import (
    ClassificationWorkload,
    ExtractionWorkload,
    GenerationWorkload,
    RAGWorkload,
    get_workload,
)


def test_workload_registry_and_interfaces():
    """All workloads format prompts and validate outputs properly."""
    cls_wl = get_workload("classification", allowed_labels=["YES", "NO"])
    assert isinstance(cls_wl, ClassificationWorkload)
    prompt = cls_wl.prepare_prompt({"input": "Is this working?"})
    assert "YES, NO" in prompt
    assert cls_wl.validate_output("YES") is True
    assert cls_wl.validate_output("MAYBE") is False

    ext_wl = get_workload("extraction", schema_fields=["name", "age"])
    assert isinstance(ext_wl, ExtractionWorkload)
    assert ext_wl.validate_output('{"name": "Alice", "age": 30}') is True
    assert ext_wl.validate_output("not json") is False

    gen_wl = get_workload("generation")
    assert isinstance(gen_wl, GenerationWorkload)
    assert gen_wl.validate_output("Some generated text") is True
    assert gen_wl.validate_output("") is False

    rag_wl = get_workload("rag")
    assert isinstance(rag_wl, RAGWorkload)
    prompt_rag = rag_wl.prepare_prompt({"context": "Docs here", "query": "What is x?"})
    assert "Docs here" in prompt_rag


def test_scorers_null_is_not_zero():
    """Invariant 1: Null is not 0. Missing inputs yield score=None, never 0.0."""
    acc = AccuracyScorer()
    res_none = acc.score(None, "EXPECTED")
    assert res_none.score is None

    brier = BrierScoreScorer()
    res_brier = brier.score("YES", True, context={})
    assert res_brier.score is None  # missing probability in context yields None

    schema_sc = JSONSchemaScorer(required_keys=["id"])
    assert schema_sc.score(None, None).score is None

    overlap = TokenOverlapScorer()
    assert overlap.score(None, "test").score is None


def test_extraction_scorers():
    """JSONSchemaScorer and FieldMatchScorer evaluate structured accuracy."""
    schema_sc = JSONSchemaScorer(required_keys=["entity", "action"])
    res_ok = schema_sc.score('{"entity": "server", "action": "restart"}', None)
    assert res_ok.score == 1.0
    assert res_ok.passed is True

    res_missing = schema_sc.score('{"entity": "server"}', None)
    assert res_missing.score == 0.5
    assert res_missing.passed is False

    field_sc = FieldMatchScorer()
    res_field = field_sc.score(
        {"a": "1", "b": "2"},
        {"a": "1", "b": "2"},
    )
    assert res_field.score == 1.0
    assert res_field.passed is True


def test_generation_scorers():
    """KeywordContainmentScorer and TokenOverlapScorer compute lexical metrics."""
    kw_sc = KeywordContainmentScorer()
    res_kw = kw_sc.score(
        "The model accurately predicts high latency in us-east-1.",
        None,
        context={"keywords": ["high latency", "us-east-1", "nonexistent"]},
    )
    assert res_kw.score == pytest.approx(2 / 3)
    assert res_kw.passed is False

    tok_sc = TokenOverlapScorer()
    res_tok = tok_sc.score("quick brown fox jumps", "quick brown fox jumps")
    assert res_tok.score == 1.0


def test_llm_judge_offline_mock_execution():
    """LLM Judge operates with local mock judge function with 0 live network calls."""
    def mock_judge(prompt: str) -> str:
        return '{"score": 5, "grounded": true, "reasoning": "Excellent factual alignment."}'

    judge = LLMJudgeScorer(judge_fn=mock_judge)
    res = judge.score("Predicted answer", "Ground truth answer", context={"query": "Test query"})

    assert res.score == 1.0  # (5 - 1) / 4 = 1.0
    assert res.passed is True
    assert res.details["raw_score_1_to_5"] == 5
    assert res.details["grounded"] is True

    # When no judge function is provided, returns None fail-closed
    judge_offline = LLMJudgeScorer(judge_fn=None)
    assert judge_offline.score("a", "b").score is None


def test_report_generation_and_caveats(tmp_path: Path):
    """ReportGenerator produces Markdown and JSON reports with cryptographic manifest and caveats."""
    manifest = RunManifest(
        run_id="run-test-001",
        plan_id="plan-test",
        plan_fingerprint="abc1234567890abcdef1234567890abcdef1234567890abcdef1234567890",
        models=["google/gemini-3.5-flash-lite"],
        dataset_path="data/evaluation/test.jsonl",
        dataset_hash="hash-1234",
        total_cases=10,
        spend_by_basis={"ACTUAL": "0.0120", "ESTIMATED": "0.0050"},
    )

    metrics = {
        "mean_accuracy": 0.80,
        "mean_latency_ms": 125.4,
    }

    gen = ReportGenerator(output_dir=tmp_path)
    md_file = gen.export_report(
        manifest=manifest,
        summary_metrics=metrics,
        unverified_cases=3,
        unresolved_spend_count=1,
        is_synthetic=True,
    )

    assert md_file.is_file()
    md_content = md_file.read_text(encoding="utf-8")
    assert "Cryptographic Run Manifest" in md_content
    assert manifest.plan_fingerprint in md_content
    assert "Small sample size (N=10)" in md_content
    assert "Ground Truth Pending: 3 cases" in md_content
    assert "Unresolved Cost: 1 requests" in md_content
    assert "Synthetic Fixture Data" in md_content

    # JSON report check
    json_file = tmp_path / f"report_{manifest.run_id}.json"
    assert json_file.is_file()
    data = json.loads(json_file.read_text(encoding="utf-8"))
    assert len(data["caveats"]) == 4

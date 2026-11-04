"""Scores are measured or absent, never invented (invariant 1: null is not 0; invariant 10: no simulation).

Covers the rubric evaluator, run-level aggregation, GenericRunner persistence, replay scoring in the
CLI, and the migration that lets run-level means be NULL.
"""

import json
import sqlite3
from pathlib import Path

from typer.testing import CliRunner

from runport.cli import app
from runport.connectors.python_target import PythonCallableTarget
from runport.core.config import settings
from runport.evaluation.evaluator import RubricEvaluator
from runport.evaluation.replay_scoring import mean_or_none, score_replay_results
from runport.runs.executor import GenericRunner
from runport.runs.planner import create_execution_plan
from runport.runs.replay import ReplayRunner
from runport.schemas.scoring import EvaluationScore
from runport.storage.db import DatabaseManager


def _score(output: str, expected):
    return RubricEvaluator().evaluate(score_id="s", execution_id="e", generated_output=output, expected_answer=expected)


# ---------- rubric evaluator ----------


def test_unlabelled_case_is_not_scored():
    s = _score("A well formed answer about refunds.", None)
    assert s.accuracy is None and s.groundedness is None and s.overall_score is None
    assert s.format_adherence == 1.0  # format is still measurable without a label
    assert "not scored" in (s.notes or "")


def test_reference_without_scorable_words_is_not_scored():
    s = _score("Yes it is.", "No")
    assert s.accuracy is None and s.groundedness is None and s.overall_score is None


def test_labelled_case_is_scored_by_overlap():
    s = _score("Containers support up to 64 GB of RAM.", "Each container supports up to 64 GB of RAM.")
    assert s.accuracy is not None and 0.0 < s.accuracy <= 1.0
    assert s.overall_score is not None


def test_empty_output_is_wrong_only_when_labelled():
    assert _score("", "Paris").accuracy == 0.0
    unlabelled = _score("", None)
    assert unlabelled.accuracy is None and unlabelled.overall_score is None


def test_composite_of_unmeasured_parts_is_unmeasured():
    score = EvaluationScore(score_id="s", execution_id="e", accuracy=None, groundedness=0.5, format_adherence=1.0)
    assert score.overall_score is None


def test_mean_or_none_ignores_missing_and_never_returns_zero_for_nothing():
    assert mean_or_none([None, None]) is None
    assert mean_or_none([]) is None
    assert mean_or_none([1.0, None, 0.0]) == 0.5


# ---------- replay scoring ----------


def test_replay_scores_recorded_outputs_and_leaves_missing_cases_empty():
    cases = [
        {"id": "c1", "query": "Capital of France?", "expected_answer": "Paris is the capital of France."},
        {"id": "c2", "query": "Capital of Italy?", "expected_answer": "Rome is the capital of Italy."},
    ]
    runner = ReplayRunner(fixtures=[{"id": "c1", "output_text": "Paris is the capital of France.", "latency_ms": 120.0}])
    rows, agg = score_replay_results("run-t", cases, runner.replay_dataset(cases))

    recorded, missing = rows
    assert recorded["accuracy"] == 1.0 and recorded["latency_ms"] == 120.0
    # the expected answer is never substituted for a missing recording
    assert missing["generated_output"] == "" and missing["accuracy"] is None and missing["latency_ms"] is None
    assert agg["completed_cases"] == 1 and agg["failed_cases"] == 1
    assert agg["mean_accuracy"] == 1.0 and agg["mean_latency_ms"] == 120.0


def test_fixture_without_output_is_a_failed_replay_with_no_latency():
    res = ReplayRunner(fixtures=[{"id": "c1", "query": "q"}]).replay_case("c1")
    assert res.is_success is False and res.output_text is None and res.latency_ms is None
    assert "no recorded output" in (res.error_message or "")


# ---------- GenericRunner ----------


def test_generic_runner_does_not_store_completion_as_accuracy(tmp_path: Path):
    ds = tmp_path / "eval.jsonl"
    ds.write_text(json.dumps({"id": "c1", "query": "hello", "expected_answer": "HELLO"}) + "\n")
    db = DatabaseManager(tmp_path / "g.db")
    db.init_db()
    target = PythonCallableTarget(target_id="upper", name="upper", func=lambda c: {"output": c["query"].upper()})
    plan = create_execution_plan(["upper"], ds, is_live=False)
    run = GenericRunner(db=db).execute_plan(plan, {"upper": target}, [{"id": "c1", "query": "hello"}])[0]

    stored_run = db.get_evaluation_run(run.run_id)
    assert stored_run["completed_cases"] == 1
    assert stored_run["mean_accuracy"] is None and stored_run["mean_overall_score"] is None
    row = db.get_evaluation_results_for_run(run.run_id)[0]
    assert row["accuracy"] is None and row["overall_score"] is None
    assert row["format_adherence"] == 1.0


# ---------- CLI replay ----------


def _seed_dataset(path: Path) -> Path:
    rows = [
        {
            "id": f"case-{i}",
            "query": f"Question {i}?",
            "expected_answer": f"Answer number {i} explains the policy.",
            "classification": "SYNTHETIC",
            "split": "TEST",
        }
        for i in range(2)
    ]
    path.write_text("\n".join(json.dumps(r) for r in rows) + "\n")
    return path


def test_cli_replay_without_recordings_reports_nothing_measured(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    ds = _seed_dataset(tmp_path / "ds.jsonl")
    r = CliRunner(env={"COLUMNS": "250"}).invoke(app, ["benchmark", "--replay", "--dataset", str(ds)])
    assert r.exit_code == 0, r.output
    assert "0 / 2" in r.output and "nothing was scored" in r.output
    assert "100.0%" not in r.output and "110" not in r.output

    db = DatabaseManager(settings.db_path)  # conftest points settings at a private temp dir
    run = db.get_all_evaluation_runs()[0]
    assert run["mean_accuracy"] is None and run["mean_latency_ms"] is None
    assert all(row["prompt"] for row in db.get_evaluation_results_for_run(run["run_id"]))  # query text is kept


def test_cli_replay_scores_recorded_fixtures(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    ds = _seed_dataset(tmp_path / "ds.jsonl")
    fx = tmp_path / "fixtures.jsonl"
    fx.write_text(
        json.dumps({"id": "case-0", "output_text": "Answer number 0 explains the policy.", "latency_ms": 200.0})
        + "\n"
        + json.dumps({"id": "case-1", "output_text": "Something unrelated entirely.", "latency_ms": 400.0})
        + "\n"
    )
    r = CliRunner(env={"COLUMNS": "250"}).invoke(app, ["benchmark", "--replay", "--dataset", str(ds), "--fixtures", str(fx)])
    assert r.exit_code == 0, r.output
    assert "2 / 2" in r.output and "300.0 ms" in r.output

    db = DatabaseManager(settings.db_path)
    run = db.get_all_evaluation_runs()[0]
    accs = sorted(row["accuracy"] for row in db.get_evaluation_results_for_run(run["run_id"]))
    assert accs[0] < 1.0 and accs[1] == 1.0
    assert run["mean_accuracy"] == round(sum(accs) / 2, 4)


# ---------- migration ----------


def test_migration_makes_run_means_nullable_and_keeps_rows(tmp_path: Path):
    path = tmp_path / "legacy.db"
    conn = sqlite3.connect(path)
    conn.executescript(
        """
        CREATE TABLE evaluation_runs (
            run_id TEXT PRIMARY KEY, timestamp TEXT NOT NULL, model_id TEXT NOT NULL, dataset_path TEXT NOT NULL,
            total_cases INTEGER NOT NULL, completed_cases INTEGER NOT NULL, failed_cases INTEGER NOT NULL,
            total_cost_usd TEXT NOT NULL, mean_latency_ms REAL NOT NULL, mean_accuracy REAL NOT NULL,
            mean_groundedness REAL NOT NULL, mean_overall_score REAL NOT NULL, is_dry_run INTEGER NOT NULL DEFAULT 1, notes TEXT
        );
        CREATE TABLE evaluation_results (
            result_id TEXT PRIMARY KEY, run_id TEXT NOT NULL, case_id TEXT NOT NULL, prompt TEXT NOT NULL,
            expected_answer TEXT, generated_output TEXT NOT NULL, latency_ms REAL, prompt_tokens INTEGER,
            completion_tokens INTEGER, cost_usd TEXT, accuracy REAL, groundedness REAL, format_adherence REAL,
            overall_score REAL, evaluator_notes TEXT, FOREIGN KEY (run_id) REFERENCES evaluation_runs(run_id)
        );
        INSERT INTO evaluation_runs VALUES ('old', 't', 'm', 'd', 1, 1, 0, '0', 10.0, 0.5, 0.5, 0.5, 1, NULL);
        INSERT INTO evaluation_results VALUES ('r1', 'old', 'c1', 'p', NULL, 'o', 10.0, NULL, NULL, NULL, 0.5, NULL, 1.0, NULL, NULL);
        """
    )
    conn.commit()
    conn.close()

    db = DatabaseManager(path)
    db.init_db()
    db.init_db()  # idempotent

    with db.get_connection() as c:
        notnull = {r[1]: r[3] for r in c.execute("PRAGMA table_info(evaluation_runs)")}
        assert not any(notnull[k] for k in ("mean_latency_ms", "mean_accuracy", "mean_groundedness", "mean_overall_score"))
        assert c.execute("SELECT mean_accuracy FROM evaluation_runs WHERE run_id='old'").fetchone()[0] == 0.5
        assert c.execute("SELECT COUNT(*) FROM evaluation_results WHERE run_id='old'").fetchone()[0] == 1
        assert c.execute("PRAGMA foreign_key_check").fetchall() == []

    db.save_evaluation_run(
        {
            "run_id": "new",
            "timestamp": "t",
            "model_id": "m",
            "dataset_path": "d",
            "total_cases": 1,
            "completed_cases": 0,
            "failed_cases": 1,
            "total_cost_usd": "0",
            "mean_latency_ms": None,
            "mean_accuracy": None,
            "mean_groundedness": None,
            "mean_overall_score": None,
            "is_dry_run": 1,
        }
    )
    run = db.get_evaluation_run("new")
    assert run["mean_accuracy"] is None and run["mean_latency_ms"] is None

#!/usr/bin/env python3
"""Benching an in-memory Python callable without network or HTTP."""

from pathlib import Path
from runport.connectors.python_target import PythonCallableTarget
from runport.runs.executor import GenericRunner
from runport.runs.planner import create_execution_plan
from runport.storage.db import DatabaseManager


def custom_pipeline(input_data: dict) -> dict:
    """Arbitrary in-process function, agent chain, or prompt pipeline."""
    text = input_data.get("text", "")
    return {
        "length": len(text),
        "tokens": len(text.split()),
        "processed": text.strip().title(),
    }


def main():
    target = PythonCallableTarget(
        target_id="python-cleaner",
        name="Title Case Pipeline",
        func=custom_pipeline,
    )

    import os
    import tempfile

    tmp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp_db.close()
    db = DatabaseManager(tmp_db.name)
    db.init_db()
    runner = GenericRunner(db=db)
    eval_file = Path(__file__).parent / "eval.jsonl"
    cases = [
        {"id": "c1", "text": "hello from the local callable target"},
        {"id": "c2", "text": "zero network calls and zero spend"},
    ]

    plan = create_execution_plan([target.target_id], eval_file, is_live=False)
    results = runner.execute_plan(plan, {target.target_id: target}, cases)
    case_results = results[0].case_results

    for case, res in zip(cases, case_results):
        print(f"[{case['id']}] Result: {res.output_text} | Latency: {res.latency_ms:.3f}ms")
        assert res.is_success

    print("\nIn-memory Python callable bench completed successfully!")
    try:
        os.unlink(tmp_db.name)
    except OSError:
        pass


if __name__ == "__main__":
    main()

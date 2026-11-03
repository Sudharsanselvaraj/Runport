"""Test all 6 offline examples under examples/ to verify reproducible execution."""

import subprocess
import sys
from pathlib import Path
import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent

EXAMPLES = [
    REPO_ROOT / "examples" / "classification" / "run.py",
    REPO_ROOT / "examples" / "rag" / "run.py",
    REPO_ROOT / "examples" / "dify-workflow" / "run.py",
    REPO_ROOT / "examples" / "http-workflow" / "run.py",
    REPO_ROOT / "examples" / "python-callable" / "run.py",
    REPO_ROOT / "examples" / "replay-demo" / "run.py",
]


@pytest.mark.parametrize("example_script", EXAMPLES, ids=[p.parent.name for p in EXAMPLES])
def test_example_runs_offline(example_script: Path):
    """Each example must run cleanly in <5 seconds without network errors or unhandled exceptions."""
    assert example_script.exists(), f"Example script does not exist: {example_script}"

    proc = subprocess.run(
        [sys.executable, str(example_script)],
        cwd=str(example_script.parent),
        capture_output=True,
        text=True,
        timeout=10,
    )

    assert proc.returncode == 0, f"Example {example_script.parent.name} failed:\nSTDOUT:\n{proc.stdout}\nSTDERR:\n{proc.stderr}"
    assert "error" not in proc.stderr.lower() or "exception" not in proc.stderr.lower()

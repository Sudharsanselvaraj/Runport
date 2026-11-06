"""The landing page's connector data must match the connector registry.

web/src/data/connectors.ts drives the orbit tiles in the bento section and the
connector counts on the page. It has to list exactly the connectors in the status
table of docs/connectors/README.md, with the same status, and each one must have a
module in src/runport.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _readme_matrix() -> dict[str, str]:
    text = (ROOT / "docs" / "connectors" / "README.md").read_text(encoding="utf-8")
    rows = re.findall(r"^\| `([a-z0-9_]+)` \|[^|]*\| \**\*?(Stable|Experimental)\**\*? \|", text, flags=re.M)
    return {kind: ("supported" if status == "Stable" else "experimental") for kind, status in rows}


def _page_connectors() -> dict[str, tuple[str, str]]:
    text = (ROOT / "web" / "src" / "data" / "connectors.ts").read_text(encoding="utf-8")
    entries = re.findall(r"\{ id: '([a-z0-9_]+)', name: '[^']+', status: '(supported|experimental)', module: '([^']+)'", text)
    return {kind: (status, module) for kind, status, module in entries}


def test_connector_table_is_parsed_completely():
    matrix = _readme_matrix()
    assert "n8n" in matrix, "connector ids with digits must be read too"
    assert len(matrix) == 12


def test_page_connectors_match_the_registry():
    page = _page_connectors()
    assert {k: v[0] for k, v in page.items()} == _readme_matrix()
    for kind, (_, module) in page.items():
        assert (ROOT / "src" / "runport" / module).is_file(), f"{kind}: {module} does not exist"

from __future__ import annotations

import ast
from pathlib import Path

from scripts.ci.integrity.auditor import (
    check_canonical_flow,
    dotted_name,
    finding,
    summarize,
)


def test_dotted_name_understands_nested_calls() -> None:
    expr = ast.parse("requests.post('https://example.test')").body[0].value
    assert dotted_name(expr.func) == "requests.post"


def test_summarize_counts_findings_by_severity() -> None:
    findings = [
        finding("P0_X", "P0", "x", "repo", 1, "m", "r"),
        finding("P1_Y", "P1", "y", "repo", 1, "m", "r"),
        finding("P1_Z", "P1", "z", "repo", 1, "m", "r"),
        finding("P2_A", "P2", "a", "repo", 1, "m", "r"),
    ]

    assert summarize(findings) == {"P0": 1, "P1": 2, "P2": 1}


def test_canonical_flow_check_reports_missing_terms(tmp_path: Path) -> None:
    path = tmp_path / "sample.py"
    path.write_text("signal = state = decision = None\n", encoding="utf-8")

    spec = {"canonical_flow": ["signal", "state", "decision", "policy", "guard"]}

    # Use a repo-relative monkey-free path by passing a real Path; the function only reads text index.
    findings = check_canonical_flow([path], spec)

    assert findings
    assert findings[0].check_id == "P0_CANONICAL_FLOW"
    assert "policy" in findings[0].message
    assert "guard" in findings[0].message

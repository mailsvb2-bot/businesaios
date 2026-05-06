from __future__ import annotations

import pytest

from tests._infra.repo_scan import REPO_ROOT, format_hits, scan_lines


@pytest.mark.lock
def test_lock_knowledge_forbids_decisioncore_imports() -> None:
    hits = scan_lines(
        patterns={
            "decisioncore_import": r"^\s*(from\s+core\.ai\.decision_core\b|import\s+core\.ai\.decision_core\b)",
        },
        root=REPO_ROOT / "core" / "knowledge",
        allowlist_relpaths=("tests/arch/test_lock_knowledge_no_decisioncore_imports.py",),
    )
    assert not hits, "core/knowledge must not import DecisionCore.\n" + format_hits(hits)
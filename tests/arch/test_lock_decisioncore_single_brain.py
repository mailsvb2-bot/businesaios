from __future__ import annotations

import pytest

from tests._infra.repo_scan import format_hits, scan_lines


@pytest.mark.lock
def test_lock_decisioncore_defined_only_once() -> None:
    """One-brain lock: DecisionCore must be defined only in core/ai/decision_core.py."""

    hits = scan_lines(
        patterns={
            "class_DecisionCore": r"^\s*class\s+DecisionCore\b",
        },
        allowlist_relpaths=(
            "core/ai/decision_core.py",
            "tests/arch/test_lock_decisioncore_single_brain.py",
        ),
    )
    assert not hits, "DecisionCore must be defined only in core/ai/decision_core.py.\n" + format_hits(hits)


@pytest.mark.lock
def test_lock_no_shadow_brain_modules_imported() -> None:
    """Small heuristic lock: prevent obvious “second brain” imports."""

    hits = scan_lines(
        patterns={
            "shadow_brain_import": (
                r"^\s*(from\s+core\.(brain|ai_brain|planner|policy_engine|autopilot_brain)\b"
                r"|import\s+core\.(brain|ai_brain|planner|policy_engine|autopilot_brain)\b)"
            ),
        },
        allowlist_relpaths=("tests/arch/test_lock_decisioncore_single_brain.py",),
    )
    assert not hits, (
        "Shadow-brain modules are forbidden. Route decision logic through core/ai/decision_core.py.\n"
        + format_hits(hits)
    )
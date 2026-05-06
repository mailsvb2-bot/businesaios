from __future__ import annotations

from tests._infra.repo_scan import format_hits, scan_lines


def test_lock_survival_controller_single_source() -> None:
    """SurvivalController must be defined in exactly one place."""

    hits = scan_lines(
        patterns={
            "DEF_SURVIVAL_CONTROLLER": r"^\s*class\s+SurvivalController\b",
        },
        include_glob="**/*.py",
        allowlist_relpaths=("survival/controller.py",),
    )
    assert hits == [], "SurvivalController must be single-source-of-truth.\n" + format_hits(hits)


def test_lock_governance_ai_single_source() -> None:
    """GovernanceAI must be defined in exactly one place."""

    hits = scan_lines(
        patterns={
            "DEF_GOVERNANCE_AI": r"^\s*class\s+GovernanceAI\b",
        },
        include_glob="**/*.py",
        allowlist_relpaths=("governance/governance_ai.py",),
    )
    assert hits == [], "GovernanceAI must be single-source-of-truth.\n" + format_hits(hits)

from __future__ import annotations

import pytest

from tests._infra.repo_scan import REPO_ROOT, format_hits, scan_lines


@pytest.mark.lock
def test_lock_reward_layer_never_issues_actions() -> None:
    hits = scan_lines(
        patterns={
            "issue_action": r"\b(issue|dispatch|execute)_action\b",
            "gateway_propose": r"\.propose\(",
            "apply_call": r"\bapply_[a-z_]+\(",
        },
        allowlist_relpaths=(
            "tests/arch/test_lock_reward_observe_no_action_issue.py",
            "core/reward/reward_engine.py",
            "core/reward/observe_flow.py",
        ),
        root=REPO_ROOT / "core" / "reward",
    )
    assert not hits, (
        "Reward layer must stay observation-only and never issue/apply actions.\n"
        + format_hits(hits)
    )

from __future__ import annotations

import pytest

from tests._infra.repo_scan import REPO_ROOT, format_hits, scan_lines


@pytest.mark.lock
def test_lock_pricing_rl_never_mutates_policy_directly() -> None:
    hits = scan_lines(
        patterns={
            "policy_write": r"\b(update_policy|set_policy|approve_policy|claim_for_apply)\b",
            "gateway_propose": r"\.propose\(",
        },
        allowlist_relpaths=(
            "tests/arch/test_lock_pricing_no_policy_mutation.py",
        ),
        root=REPO_ROOT / "core" / "pricing" / "rl",
    )
    assert not hits, (
        "Pricing RL must score/select only; policy mutation must not live here.\n"
        + format_hits(hits)
    )

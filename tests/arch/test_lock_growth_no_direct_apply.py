from __future__ import annotations

import pytest

from tests._infra.repo_scan import REPO_ROOT, format_hits, scan_lines


@pytest.mark.lock
def test_lock_growth_never_applies_directly() -> None:
    hits = scan_lines(
        patterns={
            "apply_call": r"\bapply_[a-z_]+\(",
            "service_apply": r"\._apply\b",
        },
        allowlist_relpaths=(
            "tests/arch/test_lock_growth_no_direct_apply.py",
            "autopilot_engine.py",
            "autopilot_flow.py",
        ),
        root=REPO_ROOT / "core" / "growth",
    )
    assert not hits, (
        "Growth layer must never apply directly; proposals only.\n"
        + format_hits(hits)
    )

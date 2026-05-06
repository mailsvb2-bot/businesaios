from __future__ import annotations

import pytest

from tests._infra.repo_scan import REPO_ROOT, format_hits, scan_lines


@pytest.mark.lock
def test_lock_growth_autopilot_never_applies_ads_directly() -> None:
    hits = scan_lines(
        patterns={
            "direct_apply": r"\b(_apply\b|apply_plan\s*\()",
        },
        allowlist_relpaths=(
            "tests/arch/test_lock_ads_autopilot_single_path.py",
            "autopilot_engine.py",
            "autopilot_flow.py",
        ),
        root=REPO_ROOT / "core" / "growth",
    )
    assert not hits, (
        "Growth autopilot must never apply ads changes directly. Queue proposals via gateway only.\n"
        + format_hits(hits)
    )


@pytest.mark.lock
def test_lock_runtime_handler_requires_decision_route() -> None:
    hits = scan_lines(
        patterns={
            "forbidden_env_none_path": r"\benv\s*is\s*None\b",
        },
        allowlist_relpaths=(
            "tests/arch/test_lock_ads_autopilot_single_path.py",
        ),
        root=REPO_ROOT / "runtime" / "handlers",
    )
    offenders = [
        hit for hit in hits
        if hit.relpath.endswith("ads_autopilot_tick.py")
    ]
    assert not offenders, (
        "ads_autopilot_tick handler must be envelope-routed and fail closed.\n"
        + format_hits(offenders)
    )

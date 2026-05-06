from __future__ import annotations

import pytest

from tests._infra.repo_scan import REPO_ROOT, format_hits, scan_lines


@pytest.mark.lock
def test_lock_growth_autopilot_has_no_direct_decision_issue() -> None:
    hits = scan_lines(
        patterns={
            "direct_decide": r"\b(decide|issue_decision|select_action|choose_action)\s*\(",
        },
        allowlist_relpaths=(
            "tests/arch/test_lock_ads_autopilot_no_second_brain_expansion.py",
        ),
        root=REPO_ROOT / "core" / "growth",
    )
    offenders = [
        h
        for h in hits
        if h.relpath.endswith("autopilot_engine.py") or h.relpath.endswith("autopilot_flow.py")
    ]
    assert not offenders, (
        "Growth autopilot must not grow its own decision brain.\n" + format_hits(offenders)
    )


@pytest.mark.lock
def test_lock_runtime_ads_autopilot_flow_uses_shared_loader_only() -> None:
    hits = scan_lines(
        patterns={
            "runpy_fallback": r"runpy\.run_path|spec_from_file_location",
        },
        allowlist_relpaths=(
            "tests/arch/test_lock_ads_autopilot_no_second_brain_expansion.py",
            "runtime/handlers/_module_loader.py",
            "runtime/handler_loader.py",
        ),
        root=REPO_ROOT / "runtime" / "handlers",
    )
    offenders = [h for h in hits if h.relpath.endswith("ads_autopilot_flow.py")]
    assert not offenders, (
        "ads_autopilot_flow must use the shared module loader only; no hidden fallback path.\n"
        + format_hits(offenders)
    )

from __future__ import annotations

import pytest

from tests._infra.repo_scan import REPO_ROOT, format_hits, scan_lines


@pytest.mark.lock
def test_lock_ads_autopilot_engine_no_direct_apply():
    hits = scan_lines(patterns={"apply_plan_call": r"\._ads\.apply_plan\s*\("}, allowlist_relpaths=("tests/arch/test_lock_ads_autopilot_engine_no_direct_apply.py",), root=REPO_ROOT / "core" / "ads" / "autopilot")
    assert not hits, "Ads autopilot engine must never apply directly.\n" + format_hits(hits)

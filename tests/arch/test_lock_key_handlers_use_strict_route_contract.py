from __future__ import annotations
import pytest
from tests._infra.repo_scan import REPO_ROOT, format_hits, scan_lines

@pytest.mark.lock
def test_lock_key_handlers_use_strict_route_contract() -> None:
    hits = scan_lines(patterns={"legacy_route_contract": r"extract_route_from_envelope"}, allowlist_relpaths=("tests/arch/test_lock_key_handlers_use_strict_route_contract.py", "route_contract.py"), root=REPO_ROOT / "runtime" / "handlers")
    offenders = [hit for hit in hits if hit.relpath.endswith(("ads_apply_route.py", "ai_ceo_plan_flow.py", "pricing_select.py", "reward_observe.py", "growth_propose.py"))]
    assert not offenders, "Key decision-routed handlers must use strict route extraction to avoid payload fallback drift.\n" + format_hits(offenders)

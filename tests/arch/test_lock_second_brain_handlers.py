from __future__ import annotations

import pytest

from tests._infra.repo_scan import REPO_ROOT, format_hits, scan_lines


@pytest.mark.lock
def test_lock_runtime_handlers_require_decision_route() -> None:
    hits = scan_lines(
        patterns={
            "direct_payload_decision": r'payload\.get\("decision_id"',
            "direct_payload_correlation": r'payload\.get\("correlation_id"',
        },
        allowlist_relpaths=(
            "tests/arch/test_lock_second_brain_handlers.py",
        ),
        root=REPO_ROOT / "runtime" / "handlers",
    )
    offenders = [
        hit for hit in hits
        if hit.relpath in {
            "runtime/handlers/ai_ceo_plan.py",
            "runtime/handlers/pricing_select.py",
            "runtime/handlers/reward_observe.py",
            "runtime/handlers/growth_propose.py",
        }
    ]
    assert not offenders, (
        "Critical handlers must derive route from DecisionCore envelope, not from raw payload.\n"
        + format_hits(offenders)
    )
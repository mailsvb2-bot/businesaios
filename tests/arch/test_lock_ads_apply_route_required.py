from __future__ import annotations

import pytest

from tests._infra.repo_scan import REPO_ROOT, format_hits, scan_lines


@pytest.mark.lock
def test_lock_ads_apply_execute_requires_canonical_route() -> None:
    hits = scan_lines(
        patterns={
            "direct_payload_decision_id": r'decision_id\s*=\s*str\(p\.get\(\"decision_id\"',
        },
        allowlist_relpaths=(
            "tests/arch/test_lock_ads_apply_route_required.py",
        ),
        root=REPO_ROOT / "runtime" / "handlers",
    )
    offenders = [hit for hit in hits if hit.relpath.endswith("ads_apply_execute.py")]
    assert not offenders, (
        "ads_apply_execute must use canonical route metadata, not payload fallbacks.\n"
        + format_hits(offenders)
    )

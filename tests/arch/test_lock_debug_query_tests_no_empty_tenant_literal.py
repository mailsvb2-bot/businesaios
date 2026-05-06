from __future__ import annotations

import pytest

from tests._infra.repo_scan import format_hits, scan_lines


@pytest.mark.lock
def test_lock_debug_query_tests_forbid_empty_tenant_literals() -> None:
    hits = scan_lines(
        patterns={
            "tenant_id_empty_str": r"\btenant_id\s*=\s*['\"]\s*['\"]",
        },
    )

    filtered = [
        hit
        for hit in hits
        if hit.relpath.startswith("interfaces/web/debug/")
        or hit.relpath.startswith("tests/test_messaging_policy_")
    ]

    assert not filtered, (
        "Debug/web query layers and messaging policy tests must not use empty tenant_id literals. "
        "Use tenant_id=None and let the parser normalize to 'default'.\n"
        + format_hits(filtered)
    )

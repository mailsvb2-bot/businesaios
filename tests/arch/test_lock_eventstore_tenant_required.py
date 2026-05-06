from __future__ import annotations

import pytest

from tests._infra.repo_scan import format_hits, scan_lines


@pytest.mark.lock
def test_lock_eventstore_calls_require_tenant_id_kwarg() -> None:
    """Tenant safety lock.

    - iter_events(...) and count_events(...) must always pass tenant_id=... when calling an EventStore.
    - No implicit tenant defaults.

    Heuristic scope:
    - Targets common receiver names (event_store/store/es).
    - Excludes tools/** because scripts often use multiline calls.
    """

    allow = (
        # Port + implementations define these methods and may reference their signature.
        "contracts/event_store.py",
        # Multiline calls in retention arms already pass tenant_id=..., but the regex here is line-based.
        "core/retention/arms.py",
        "runtime/platform/event_store/sqlite_event_store.py",
        "runtime/platform/event_store/postgres_event_store.py",
        "runtime/platform/event_store/memory_event_store.py",
        "tests/arch/test_lock_eventstore_tenant_required.py",
    )

    hits = scan_lines(
        patterns={
            "iter_events_missing_tenant_id": r"\b(event_store|store|es)\.iter_events\s*\(\s*(?![^)]*\btenant_id\s*=)",
            "count_events_missing_tenant_id": r"\b(event_store|store|es)\.count_events\s*\(\s*(?![^)]*\btenant_id\s*=)",
        },
        exclude_glob="tools/**",
        allowlist_relpaths=allow,
    )

    assert not hits, (
        "EventStore calls must be tenant-explicit (tenant_id=...).\n" + "Violations:\n" + format_hits(hits)
    )


@pytest.mark.lock
def test_lock_no_empty_tenant_id_literals() -> None:
    """Empty tenant_id literals are forbidden in production code.

    Exceptions:
    - runtime/boot/tenant_hard_gate.py uses tenant_id="" as an explicit probe for the startup hard-gate.
    - tests/test_tenant_strictness.py intentionally exercises the empty-tenant rejection.
    """

    hits = scan_lines(
        patterns={
            "tenant_id_empty_str": r"\btenant_id\s*=\s*['\"]\s*['\"]",
        },
        allowlist_relpaths=(
            "tests/arch/test_lock_eventstore_tenant_required.py",
            "runtime/boot/tenant_hard_gate.py",
            "tests/test_tenant_strictness.py",
        ),
    )

    assert not hits, "Empty tenant_id literals are forbidden.\n" + format_hits(hits)

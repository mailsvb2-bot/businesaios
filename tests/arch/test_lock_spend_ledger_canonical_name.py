from __future__ import annotations

import pytest

from tests._infra.repo_scan import REPO_ROOT, format_hits, scan_lines


@pytest.mark.lock
def test_lock_no_runtime_imports_from_spend_ledger_eventstore_shim() -> None:
    hits = scan_lines(
        patterns={"shim_import": r"spend_ledger_eventstore"},
        allowlist_relpaths=(
            "tests/arch/test_lock_spend_ledger_canonical_name.py",
            "core/growth/__init__.py",
        ),
        root=REPO_ROOT,
    )
    assert not hits, (
        "Use canonical core.growth.spend_ledger_event_store import path; shim name must not spread.\n"
        + format_hits(hits)
    )

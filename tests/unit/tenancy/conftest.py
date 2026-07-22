from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

import tenancy.tenant_migration_lock_sqlite as sqlite_module


_FIXED_TENANT_LOCK_NOW = datetime(2026, 7, 22, 8, 0, tzinfo=UTC)
_FIXED_CLOCK_TEST = "test_tenant_migration_lock_sqlite_coverage_wave35.py"


@pytest.fixture(autouse=True)
def isolate_tenant_lock_coverage_clock(
    request: pytest.FixtureRequest,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Keep the historical fixed-time regression wall independent of suite duration."""

    if Path(str(request.node.fspath)).name != _FIXED_CLOCK_TEST:
        return
    monkeypatch.setattr(sqlite_module, "utc_now", lambda: _FIXED_TENANT_LOCK_NOW)

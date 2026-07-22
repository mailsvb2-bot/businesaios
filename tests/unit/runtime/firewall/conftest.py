from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def enable_singleton_lock_for_firewall_tests(monkeypatch: pytest.MonkeyPatch) -> None:
    """Do not let an ambient full-CI debug flag disable lock assertions."""

    monkeypatch.delenv("DISABLE_SINGLETON_LOCK", raising=False)

from __future__ import annotations

from tests.arch._canon_exception_registry_guard import load_registry


def test_exception_registry_entries_are_complete() -> None:
    for item in load_registry():
        assert item.exception_id.strip()
        assert item.scope.strip()
        assert item.reason.strip()
        assert item.owner.strip()
        assert item.created_on.strip()
        assert item.expires_on.strip()
        assert item.canonical_rule.strip()
        assert item.paths
        assert item.status.strip()

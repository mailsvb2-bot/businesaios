from __future__ import annotations
from tests.arch._canon_migration_registry_guard import load_registry

def test_migration_registry_entries_are_complete() -> None:
    for item in load_registry():
        assert item.migration_id.strip()
        assert item.kind.strip()
        assert item.scope.strip()
        assert item.reason.strip()
        assert item.owner.strip()
        assert item.created_on.strip()
        assert item.target_date.strip()
        assert item.status.strip()
        assert item.from_paths
        assert item.to_paths
        assert item.canonical_target.strip()

from __future__ import annotations
from tests.arch._canon_migration_registry_guard import load_registry

def test_migration_registry_ids_are_unique() -> None:
    seen = set()
    offenders = []
    for item in load_registry():
        if item.migration_id in seen:
            offenders.append(item.migration_id)
        seen.add(item.migration_id)
    assert not offenders, "Migration registry contains duplicate migration_id values. Offenders:\n- " + "\n- ".join(offenders)

from __future__ import annotations
from tests.arch._canon_migration_registry_guard import load_registry

def test_migration_registry_is_loadable() -> None:
    load_registry()

from __future__ import annotations

from tests.arch._canon_migration_registry_guard import ALLOWED_KINDS, load_registry


def test_migration_registry_kinds_are_allowed() -> None:
    offenders = [f"{item.migration_id}: {item.kind}" for item in load_registry() if item.kind not in ALLOWED_KINDS]
    assert not offenders, "Migration registry contains unsupported kinds. Offenders:\n- " + "\n- ".join(offenders)

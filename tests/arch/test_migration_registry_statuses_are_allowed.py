from __future__ import annotations

from tests.arch._canon_migration_registry_guard import ALLOWED_STATUSES, load_registry


def test_migration_registry_statuses_are_allowed() -> None:
    offenders = [f"{item.migration_id}: {item.status}" for item in load_registry() if item.status not in ALLOWED_STATUSES]
    assert not offenders, "Migration registry contains unsupported statuses. Offenders:\n- " + "\n- ".join(offenders)

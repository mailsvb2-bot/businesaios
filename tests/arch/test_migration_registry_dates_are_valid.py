from __future__ import annotations
from tests.arch._canon_migration_registry_guard import load_registry

def test_migration_registry_dates_are_valid() -> None:
    offenders = []
    for item in load_registry():
        if item.target() < item.created_date():
            offenders.append(f"{item.migration_id}: target_date {item.target_date} is earlier than created_on {item.created_on}")
    assert not offenders, "Migration registry contains invalid date ranges. Offenders:\n- " + "\n- ".join(offenders)

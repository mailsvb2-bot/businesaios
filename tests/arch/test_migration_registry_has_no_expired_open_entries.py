from __future__ import annotations
from datetime import date
from tests.arch._canon_migration_registry_guard import load_registry

OPEN_STATUSES = {"planned", "active", "blocked"}

def test_migration_registry_has_no_expired_open_entries() -> None:
    today = date.today()
    offenders = []
    for item in load_registry():
        if item.status in OPEN_STATUSES and item.is_expired(today):
            offenders.append(f"{item.migration_id}: {item.status} migration expired on {item.target_date} (today is {today.isoformat()})")
    assert not offenders, "Migration registry contains expired open migrations. Offenders:\n- " + "\n- ".join(offenders)

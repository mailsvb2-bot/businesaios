from __future__ import annotations

from datetime import date

from tests.arch._canon_migration_registry_guard import load_registry


def test_migration_registry_completed_entries_are_past_or_present() -> None:
    today = date.today()
    offenders = []
    for item in load_registry():
        if item.status == "completed" and item.target() > today:
            offenders.append(f"{item.migration_id}: completed migration has future target_date {item.target_date}")
    assert not offenders, "Completed migration entries should not look like future unfinished work. Offenders:\n- " + "\n- ".join(offenders)

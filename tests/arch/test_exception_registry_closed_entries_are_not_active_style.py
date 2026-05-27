from __future__ import annotations

from datetime import date

from tests.arch._canon_exception_registry_guard import load_registry


def test_exception_registry_closed_entries_are_not_active_style() -> None:
    today = date.today()
    offenders = []
    for item in load_registry():
        if item.status == "closed" and item.expires_date() > today:
            offenders.append(f"{item.exception_id}: closed entry still expires in the future ({item.expires_on})")
    assert not offenders, "Closed exception entries should not look like still-active future exceptions. Offenders:\n- " + "\n- ".join(offenders)

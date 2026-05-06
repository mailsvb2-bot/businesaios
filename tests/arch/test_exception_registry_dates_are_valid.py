from __future__ import annotations
from tests.arch._canon_exception_registry_guard import load_registry

def test_exception_registry_dates_are_valid() -> None:
    offenders = []
    for item in load_registry():
        if item.expires_date() < item.created_date():
            offenders.append(f"{item.exception_id}: expires_on {item.expires_on} is earlier than created_on {item.created_on}")
    assert not offenders, "Exception registry contains invalid date ranges. Offenders:\n- " + "\n- ".join(offenders)

from __future__ import annotations
from datetime import date
from tests.arch._canon_exception_registry_guard import load_registry

def test_exception_registry_has_no_expired_active_entries() -> None:
    today = date.today()
    offenders = []
    for item in load_registry():
        if item.status == "active" and item.is_expired(today):
            offenders.append(f"{item.exception_id}: expired on {item.expires_on} (today is {today.isoformat()})")
    assert not offenders, "Exception registry contains expired active exceptions. Offenders:\n- " + "\n- ".join(offenders)

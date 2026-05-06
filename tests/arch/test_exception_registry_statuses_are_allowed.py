from __future__ import annotations
from tests.arch._canon_exception_registry_guard import ALLOWED_STATUSES, load_registry

def test_exception_registry_statuses_are_allowed() -> None:
    offenders = [f"{item.exception_id}: {item.status}" for item in load_registry() if item.status not in ALLOWED_STATUSES]
    assert not offenders, "Exception registry contains unsupported statuses. Offenders:\n- " + "\n- ".join(offenders)

from __future__ import annotations

from tests.arch._canon_exception_registry_guard import load_registry


def test_exception_registry_ids_are_unique() -> None:
    seen = set()
    offenders = []
    for item in load_registry():
        if item.exception_id in seen:
            offenders.append(item.exception_id)
        seen.add(item.exception_id)
    assert not offenders, "Exception registry contains duplicate exception_id values. Offenders:\n- " + "\n- ".join(offenders)

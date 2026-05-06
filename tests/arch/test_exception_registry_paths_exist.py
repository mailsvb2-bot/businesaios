from __future__ import annotations
from tests.arch._canon_exception_registry_guard import ROOT, load_registry

def test_exception_registry_paths_exist() -> None:
    offenders = []
    for item in load_registry():
        for rel in item.paths:
            if not (ROOT / rel).exists():
                offenders.append(f"{item.exception_id}: missing path {rel}")
    assert not offenders, "Exception registry references paths that do not exist. Offenders:\n- " + "\n- ".join(offenders)

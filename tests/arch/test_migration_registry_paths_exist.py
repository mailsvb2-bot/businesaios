from __future__ import annotations

from tests.arch._canon_migration_registry_guard import ROOT, load_registry


def test_migration_registry_paths_exist() -> None:
    offenders = []
    for item in load_registry():
        for rel in item.from_paths:
            if not (ROOT / rel).exists():
                offenders.append(f"{item.migration_id}: missing from_path {rel}")
        for rel in item.to_paths:
            if not (ROOT / rel).exists():
                offenders.append(f"{item.migration_id}: missing to_path {rel}")
    assert not offenders, "Migration registry references paths that do not exist. Offenders:\n- " + "\n- ".join(offenders)

from __future__ import annotations
from tests.arch._canon_arch_audit_index import absolute_path

REQUIRED_NEW_FILES = (
    "docs/CANON_MIGRATION_DEPRECATION_REGISTRY_V1.md",
    "docs/CANON_MIGRATION_DEPRECATION_REGISTRY_DATA_V1.yaml",
    "tests/arch/_canon_migration_registry_guard.py",
    "tests/arch/test_migration_registry_file_present.py",
    "tests/arch/test_migration_registry_is_loadable.py",
    "tests/arch/test_migration_registry_entries_are_complete.py",
    "tests/arch/test_migration_registry_kinds_are_allowed.py",
    "tests/arch/test_migration_registry_statuses_are_allowed.py",
    "tests/arch/test_migration_registry_dates_are_valid.py",
    "tests/arch/test_migration_registry_has_no_expired_open_entries.py",
    "tests/arch/test_migration_registry_paths_exist.py",
    "tests/arch/test_migration_registry_ids_are_unique.py",
    "tests/arch/test_migration_registry_completed_entries_are_past_or_present.py",
)

def test_arch_audit_index_tracks_migration_registry_pack() -> None:
    missing = [rel for rel in REQUIRED_NEW_FILES if not absolute_path(rel).exists()]
    assert not missing, "Canonical migration/deprecation registry pack is incomplete. Missing:\n- " + "\n- ".join(missing)

from __future__ import annotations

from tests.arch._canon_arch_audit_index import absolute_path

REQUIRED_NEW_FILES = (
    "docs/CANON_EXCEPTION_REGISTRY_V1.md",
    "docs/CANON_EXCEPTION_REGISTRY_DATA_V1.yaml",
    "tests/arch/_canon_exception_registry_guard.py",
    "tests/arch/test_exception_registry_file_present.py",
    "tests/arch/test_exception_registry_is_loadable.py",
    "tests/arch/test_exception_registry_entries_are_complete.py",
    "tests/arch/test_exception_registry_statuses_are_allowed.py",
    "tests/arch/test_exception_registry_dates_are_valid.py",
    "tests/arch/test_exception_registry_has_no_expired_active_entries.py",
    "tests/arch/test_exception_registry_paths_exist.py",
    "tests/arch/test_exception_registry_closed_entries_are_not_active_style.py",
    "tests/arch/test_exception_registry_ids_are_unique.py",
)

def test_arch_audit_index_tracks_exception_registry_pack() -> None:
    missing = [rel for rel in REQUIRED_NEW_FILES if not absolute_path(rel).exists()]
    assert not missing, "Canonical exception registry pack is incomplete. Missing:\n- " + "\n- ".join(missing)

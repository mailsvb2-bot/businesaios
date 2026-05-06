from __future__ import annotations
from tests.arch._canon_arch_audit_index import absolute_path

REQUIRED_NEW_FILES = (
    "docs/CANON_MASTER_CHECKLIST_V1.md",
    "docs/CANON_MASTER_LAYER_V1.md",
    "tests/arch/_canon_master_audit_guard.py",
    "tests/arch/test_master_audit_stack_is_consistent.py",
    "tests/arch/test_master_layer_files_present.py",
    "tests/arch/test_master_layer_files_have_explicit_markers.py",
)

def test_arch_audit_index_tracks_master_layer_pack() -> None:
    missing = [rel for rel in REQUIRED_NEW_FILES if not absolute_path(rel).exists()]
    assert not missing, "Canonical master layer pack is incomplete. Missing:\n- " + "\n- ".join(missing)

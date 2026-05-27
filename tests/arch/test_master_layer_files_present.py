from __future__ import annotations

from tests.arch._canon_arch_audit_index import absolute_path

REQUIRED_MASTER_FILES = (
    "docs/CANON_MASTER_CHECKLIST_V1.md",
    "docs/CANON_MASTER_LAYER_V1.md",
    "tests/arch/_canon_master_audit_guard.py",
    "tests/arch/test_master_audit_stack_is_consistent.py",
)

def test_master_layer_files_present() -> None:
    missing = [rel for rel in REQUIRED_MASTER_FILES if not absolute_path(rel).exists()]
    assert not missing, "Master layer files are missing. Missing:\n- " + "\n- ".join(missing)

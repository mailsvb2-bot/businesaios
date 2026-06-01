from __future__ import annotations

from tests.arch._canon_arch_audit_index import absolute_path

TARGET_FILES = (
    "docs/CANON_MASTER_CHECKLIST_V1.md",
    "docs/CANON_MASTER_LAYER_V1.md",
    "tests/arch/_canon_master_audit_guard.py",
)

def test_master_layer_files_have_explicit_markers() -> None:
    offenders = []
    for rel in TARGET_FILES:
        text = absolute_path(rel).read_text(encoding="utf-8")
        if "CANON_MASTER_LAYER" not in text:
            offenders.append(rel)
    assert not offenders, "Master layer files must contain CANON_MASTER_LAYER. Offenders:\n- " + "\n- ".join(offenders)

from __future__ import annotations
from tests.arch._canon_arch_audit_index import absolute_path

REQUIRED_NEW_FILES = (
    "docs/CANON_BOOT_RUNTIME_REGISTRY_AUDIT_V1.md",
    "docs/CANON_BOOT_RUNTIME_REGISTRY_REMEDIATION_V1.md",
    "tests/arch/_canon_boot_runtime_registry_guard.py",
    "tests/arch/test_boot_registry_public_entrypoints_have_markers.py",
    "tests/arch/test_boot_registry_public_entrypoints_have_real_entrypoints.py",
    "tests/arch/test_handler_registry_public_entrypoints_have_markers.py",
    "tests/arch/test_handler_registry_public_entrypoints_have_real_entrypoints.py",
    "tests/arch/test_boot_runtime_registry_not_empty.py",
)

def test_arch_audit_index_tracks_boot_runtime_registry_pack() -> None:
    missing = [rel for rel in REQUIRED_NEW_FILES if not absolute_path(rel).exists()]
    assert not missing, "Boot/runtime registry audit pack is incomplete. Missing:\n- " + "\n- ".join(missing)

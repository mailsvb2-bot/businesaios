from __future__ import annotations

from tests.arch._canon_arch_audit_index import absolute_path

REQUIRED_NEW_FILES = (
    "docs/CANON_META_PACK_INDEX_V1.md",
    "docs/CANON_ONBOARDING_FOR_ARCHITECTS_V1.md",
    "docs/CANON_META_PACK_MANIFEST_V1.yaml",
    "tests/arch/_canon_meta_pack_guard.py",
    "tests/arch/test_meta_pack_index_present.py",
    "tests/arch/test_meta_pack_onboarding_present.py",
    "tests/arch/test_meta_pack_manifest_is_loadable.py",
    "tests/arch/test_meta_pack_manifest_lists_required_packs.py",
    "tests/arch/test_meta_pack_manifest_paths_exist.py",
    "tests/arch/test_meta_pack_files_explicitly_reference_meta_pack.py",
)

def test_arch_audit_index_tracks_meta_pack() -> None:
    missing = []
    for rel in REQUIRED_NEW_FILES:
        if not absolute_path(rel).exists():
            missing.append(rel)
    assert not missing, "Canonical meta-pack is incomplete. Missing:\n- " + "\n- ".join(missing)

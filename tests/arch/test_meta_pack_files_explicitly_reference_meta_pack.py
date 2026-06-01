from __future__ import annotations

from tests.arch._canon_meta_pack_guard import absolute


def test_meta_pack_files_explicitly_reference_meta_pack() -> None:
    target_files = [
        "docs/CANON_META_PACK_INDEX_V1.md",
        "docs/CANON_ONBOARDING_FOR_ARCHITECTS_V1.md",
        "docs/CANON_META_PACK_MANIFEST_V1.yaml",
        "tests/arch/_canon_meta_pack_guard.py",
    ]
    offenders = []
    for rel in target_files:
        text = absolute(rel).read_text(encoding="utf-8")
        if "CANON_META_PACK" not in text:
            offenders.append(rel)
    assert not offenders, "Meta-pack core files must explicitly reference CANON_META_PACK. Offenders:\n- " + "\n- ".join(offenders)

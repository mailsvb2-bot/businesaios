from __future__ import annotations

from tests.arch._canon_meta_pack_guard import load_manifest


def test_meta_pack_manifest_is_loadable() -> None:
    manifest = load_manifest()
    assert manifest.marker == "CANON_META_PACK"
    assert manifest.meta_pack_id
    assert manifest.index_doc
    assert manifest.onboarding_doc
    assert manifest.packs

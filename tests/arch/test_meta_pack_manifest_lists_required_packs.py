from __future__ import annotations

from tests.arch._canon_meta_pack_guard import REQUIRED_PACK_IDS, load_manifest


def test_meta_pack_manifest_lists_required_packs() -> None:
    manifest = load_manifest()
    pack_ids = {pack.pack_id for pack in manifest.packs}
    missing = [pack_id for pack_id in REQUIRED_PACK_IDS if pack_id not in pack_ids]
    assert not missing, "Meta-pack manifest missing required pack ids:\n- " + "\n- ".join(missing)

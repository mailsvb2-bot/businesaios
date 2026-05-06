from __future__ import annotations

from tests.arch._canon_meta_pack_guard import absolute, all_manifest_paths, load_manifest


def test_meta_pack_manifest_paths_exist() -> None:
    manifest = load_manifest()
    missing = [rel for rel in all_manifest_paths(manifest) if not absolute(rel).exists()]
    assert not missing, "Meta-pack manifest references missing paths:\n- " + "\n- ".join(missing)

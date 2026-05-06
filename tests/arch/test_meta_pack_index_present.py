from __future__ import annotations
from tests.arch._canon_meta_pack_guard import INDEX_PATH

def test_meta_pack_index_present() -> None:
    assert INDEX_PATH.exists(), "Missing docs/CANON_META_PACK_INDEX_V1.md"

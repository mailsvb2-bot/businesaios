from __future__ import annotations

import pytest

from execution.business_operating_memory import FileBusinessOperatingMemoryStore


def test_business_memory_load_fails_closed_on_corrupt_json(tmp_path) -> None:
    store = FileBusinessOperatingMemoryStore(root_dir=tmp_path / "memory")
    target_dir = tmp_path / "memory" / "tenant-1"
    target_dir.mkdir(parents=True, exist_ok=True)
    target_file = target_dir / "biz-1.json"
    original = "{broken json"
    target_file.write_text(original, encoding="utf-8")

    with pytest.raises(ValueError, match="corrupt business memory persistence"):
        store.load(tenant_id="tenant-1", business_id="biz-1")

    assert target_file.read_text(encoding="utf-8") == original

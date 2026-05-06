from __future__ import annotations

from execution.business_operating_memory import FileBusinessOperatingMemoryStore


def test_business_memory_load_fails_closed_on_corrupt_json(tmp_path) -> None:
    store = FileBusinessOperatingMemoryStore(root_dir=tmp_path / 'memory')
    target_dir = tmp_path / 'memory' / 'tenant-1'
    target_dir.mkdir(parents=True, exist_ok=True)
    target_file = target_dir / 'biz-1.json'
    target_file.write_text('{broken json', encoding='utf-8')
    loaded = store.load(tenant_id='tenant-1', business_id='biz-1')
    assert loaded.tenant_id == 'tenant-1'
    assert loaded.business_id == 'biz-1'
    assert loaded.total_runs == 0
    assert loaded.last_run is None

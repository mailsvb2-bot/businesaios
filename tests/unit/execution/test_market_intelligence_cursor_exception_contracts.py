from __future__ import annotations

from pathlib import Path

import pytest

from execution.market_intelligence_cursor_store import PersistentMarketIntelligenceCursorStore


def test_malformed_cursor_json_is_tolerated(tmp_path: Path) -> None:
    store = PersistentMarketIntelligenceCursorStore(root_dir=tmp_path)
    path = store._path(tenant_id='tenant-1', provider='provider', source_family='search', scope_key='global')
    path.parent.mkdir(parents=True)
    path.write_text('{bad-json', encoding='utf-8')

    cursor = store.load(tenant_id='tenant-1', provider='provider', source_family='search', scope_key='global')

    assert cursor.tenant_id == 'tenant-1'
    assert cursor.cursor is None


def test_cursor_read_os_error_is_visible(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    store = PersistentMarketIntelligenceCursorStore(root_dir=tmp_path)
    path = store._path(tenant_id='tenant-1', provider='provider', source_family='search', scope_key='global')
    path.parent.mkdir(parents=True)
    path.write_text('{}', encoding='utf-8')
    original_read_text = Path.read_text

    def _read_text(self: Path, *args, **kwargs):
        if self == path:
            raise OSError('cursor disk unavailable')
        return original_read_text(self, *args, **kwargs)

    monkeypatch.setattr(Path, 'read_text', _read_text)

    with pytest.raises(OSError, match='cursor disk unavailable'):
        store.load(tenant_id='tenant-1', provider='provider', source_family='search', scope_key='global')


def test_snapshot_skips_only_malformed_json(tmp_path: Path) -> None:
    store = PersistentMarketIntelligenceCursorStore(root_dir=tmp_path)
    valid = tmp_path / 'valid.json'
    invalid = tmp_path / 'invalid.json'
    valid.write_text('{"tenant_id":"tenant-1"}', encoding='utf-8')
    invalid.write_text('{bad-json', encoding='utf-8')

    assert store.snapshot() == ({'tenant_id': 'tenant-1'},)


def test_snapshot_read_os_error_is_visible(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    store = PersistentMarketIntelligenceCursorStore(root_dir=tmp_path)
    path = tmp_path / 'cursor.json'
    path.write_text('{}', encoding='utf-8')
    original_read_text = Path.read_text

    def _read_text(self: Path, *args, **kwargs):
        if self == path:
            raise OSError('cursor snapshot disk unavailable')
        return original_read_text(self, *args, **kwargs)

    monkeypatch.setattr(Path, 'read_text', _read_text)

    with pytest.raises(OSError, match='cursor snapshot disk unavailable'):
        store.snapshot()

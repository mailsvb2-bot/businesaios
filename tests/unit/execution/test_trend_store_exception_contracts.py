from __future__ import annotations

import json
from pathlib import Path

import pytest

import execution.market_intelligence_trend_engine as trend_module
from execution.market_intelligence_trend_engine import FileTrendStore


def _path(store: FileTrendStore) -> Path:
    path = store.root_dir / 'tenant-1' / 'entity-1__score.jsonl'
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _valid_payload(**overrides):
    payload = {
        'tenant_id': 'tenant-1',
        'entity_id': 'entity-1',
        'metric': 'score',
        'value': 1.5,
        'observed_at': '2026-08-04T00:00:00+00:00',
        'metadata': {},
    }
    payload.update(overrides)
    return payload


def test_malformed_json_line_is_skipped(tmp_path: Path) -> None:
    store = FileTrendStore(root_dir=tmp_path)
    path = _path(store)
    path.write_text('{bad json\n' + json.dumps(_valid_payload()) + '\n', encoding='utf-8')

    rows = store.load(tenant_id='tenant-1', entity_id='entity-1', metric='score')

    assert len(rows) == 1


def test_invalid_trend_payload_is_skipped(tmp_path: Path) -> None:
    store = FileTrendStore(root_dir=tmp_path)
    path = _path(store)
    path.write_text(json.dumps(_valid_payload(value='not-a-number')) + '\n', encoding='utf-8')

    assert store.load(tenant_id='tenant-1', entity_id='entity-1', metric='score') == ()


def test_unknown_trend_fields_are_skipped(tmp_path: Path) -> None:
    store = FileTrendStore(root_dir=tmp_path)
    path = _path(store)
    path.write_text(json.dumps(_valid_payload(unexpected=True)) + '\n', encoding='utf-8')

    assert store.load(tenant_id='tenant-1', entity_id='entity-1', metric='score') == ()


def test_unexpected_trend_constructor_failure_is_visible(tmp_path: Path, monkeypatch) -> None:
    store = FileTrendStore(root_dir=tmp_path)
    path = _path(store)
    path.write_text(json.dumps(_valid_payload()) + '\n', encoding='utf-8')

    def _broken_trend_point(**_payload):
        raise OSError('trend dependency unavailable')

    monkeypatch.setattr(trend_module, 'TrendPoint', _broken_trend_point)

    with pytest.raises(OSError, match='trend dependency unavailable'):
        store.load(tenant_id='tenant-1', entity_id='entity-1', metric='score')

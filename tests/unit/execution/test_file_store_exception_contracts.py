from __future__ import annotations

import json
from pathlib import Path

import pytest

from execution.market_intelligence_human_feedback import HumanFeedbackStore
from execution.owner_path.owner_path_service import FileOwnerPathStore


def test_human_feedback_malformed_json_line_is_skipped(tmp_path: Path) -> None:
    store = HumanFeedbackStore(root_dir=tmp_path)
    path = tmp_path / 'tenant-1' / 'entity-1.jsonl'
    path.parent.mkdir(parents=True, exist_ok=True)
    valid = {
        'tenant_id': 'tenant-1',
        'entity_id': 'entity-1',
        'label': 'useful',
        'score_delta': 0.25,
    }
    path.write_text('{bad json\n' + json.dumps(valid) + '\n', encoding='utf-8')

    events = store.load(tenant_id='tenant-1', entity_id='entity-1')

    assert len(events) == 1
    assert events[0].label == 'useful'


def test_human_feedback_storage_failure_is_visible(tmp_path: Path, monkeypatch) -> None:
    store = HumanFeedbackStore(root_dir=tmp_path)
    path = tmp_path / 'tenant-1' / 'entity-1.jsonl'
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text('{}', encoding='utf-8')
    monkeypatch.setattr(Path, 'read_text', lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError('feedback disk unavailable')))

    with pytest.raises(OSError, match='feedback disk unavailable'):
        store.load(tenant_id='tenant-1', entity_id='entity-1')


def test_owner_path_corrupt_json_is_tolerated(tmp_path: Path) -> None:
    store = FileOwnerPathStore(root_dir=tmp_path)
    path = store._path(tenant_id='tenant-1', business_id='business-1')
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text('{bad json', encoding='utf-8')

    assert store.load(tenant_id='tenant-1', business_id='business-1') == {}


def test_owner_path_disappearing_after_exists_check_is_tolerated(tmp_path: Path, monkeypatch) -> None:
    store = FileOwnerPathStore(root_dir=tmp_path)
    path = store._path(tenant_id='tenant-1', business_id='business-1')
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text('{}', encoding='utf-8')
    monkeypatch.setattr(Path, 'read_text', lambda *_args, **_kwargs: (_ for _ in ()).throw(FileNotFoundError('gone')))

    assert store.load(tenant_id='tenant-1', business_id='business-1') == {}


def test_owner_path_storage_failure_is_visible(tmp_path: Path, monkeypatch) -> None:
    store = FileOwnerPathStore(root_dir=tmp_path)
    path = store._path(tenant_id='tenant-1', business_id='business-1')
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text('{}', encoding='utf-8')
    monkeypatch.setattr(Path, 'read_text', lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError('owner path disk unavailable')))

    with pytest.raises(OSError, match='owner path disk unavailable'):
        store.load(tenant_id='tenant-1', business_id='business-1')

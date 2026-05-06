from __future__ import annotations

import json

from application.business_autonomy.guarded_service import _read_document_state, _write_document_state


def test_distributed_state_version_increments_and_conflict_detected(tmp_path) -> None:
    path = tmp_path / 'doc.json'
    state = _read_document_state(path)
    assert state['version'] == 0
    _write_document_state(path, {'a': {'x': 1}}, expected_version=0)
    payload = json.loads(path.read_text(encoding='utf-8'))
    assert payload['version'] == 1
    try:
        _write_document_state(path, {'b': {'x': 2}}, expected_version=0)
    except RuntimeError as exc:
        assert str(exc) == 'business_autonomy_distributed_state_version_conflict'
    else:
        raise AssertionError('expected version conflict')



def test_distributed_state_write_is_atomic(tmp_path) -> None:
    path = tmp_path / 'nested' / 'doc.json'
    _write_document_state(path, {'a': {'x': 1}}, expected_version=0)
    assert path.exists()
    assert not path.with_suffix(path.suffix + '.tmp').exists()
    payload = json.loads(path.read_text(encoding='utf-8'))
    assert payload['items']['a']['x'] == 1

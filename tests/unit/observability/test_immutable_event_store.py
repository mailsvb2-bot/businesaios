from __future__ import annotations

import json
from pathlib import Path

import pytest

from observability.immutable_event_store import ImmutableEventStore


def test_immutable_event_store_detects_tamper(tmp_path: Path) -> None:
    store = ImmutableEventStore(tmp_path / 'security.jsonl')
    store.append(event_id='e1', tenant_id='tenant-1', event_type='security.login', emitted_at='2026-04-08T00:00:00+00:00', payload={'ok': True})
    store.append(event_id='e2', tenant_id='tenant-1', event_type='security.logout', emitted_at='2026-04-08T00:05:00+00:00', payload={'ok': True})
    store.validate_chain()

    rows = store.path.read_text(encoding='utf-8').splitlines()
    tampered = json.loads(rows[1])
    tampered['payload']['ok'] = False
    rows[1] = json.dumps(tampered, ensure_ascii=False, sort_keys=True)
    store.path.write_text('\n'.join(rows) + '\n', encoding='utf-8')

    with pytest.raises(ValueError, match='record_hash mismatch'):
        store.validate_chain()


def test_immutable_event_store_rejects_duplicate_event_id(tmp_path: Path) -> None:
    store = ImmutableEventStore(tmp_path / 'security.jsonl')
    store.append(event_id='e1', tenant_id='tenant-1', event_type='security.login', emitted_at='2026-04-08T00:00:00+00:00', payload={})
    with pytest.raises(ValueError, match='duplicate event_id'):
        store.append(event_id='e1', tenant_id='tenant-1', event_type='security.login', emitted_at='2026-04-08T00:00:01+00:00', payload={})

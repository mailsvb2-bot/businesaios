from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from reliability.outbox_backend import OutboxDeliveryConflict, OutboxDeliveryStatus
from reliability.outbox_sqlite_backend import SQLiteOutboxBackend, _canonical_payload_json, _json_default, _payload_digest
from reliability.outbox_store import OutboxMessage

NOW = datetime(2026, 7, 18, tzinfo=UTC)


def _message(**changes):
    values = dict(tenant_id='tenant-a', message_id='message-a', topic='topic-a', dedupe_key='dedupe-a',
                  payload={'value': 1, 'at': NOW}, created_at=NOW, updated_at=NOW, available_at=NOW,
                  trace_id='trace', run_id='run', decision_id='decision')
    values.update(changes)
    return OutboxMessage(**values)


def test_json_helpers_are_canonical_and_fail_closed() -> None:
    assert _json_default(NOW) == NOW.isoformat()
    with pytest.raises(TypeError): _json_default(object())
    assert _canonical_payload_json({'b': 2, 'a': 1}) == '{"a":1,"b":2}'
    assert len(_payload_digest({'a': 1})) == 64


def test_delivery_identity_dedupe_conflicts_and_tenant_isolation(tmp_path: Path) -> None:
    backend = SQLiteOutboxBackend(tmp_path/'outbox.sqlite3')
    health = backend.healthcheck(); assert health.healthy and health.detail.endswith('outbox.sqlite3')
    message = _message()
    receipt = backend.deliver(message)
    assert receipt.status is OutboxDeliveryStatus.DELIVERED
    duplicate = backend.deliver(message)
    assert duplicate.status is OutboxDeliveryStatus.DUPLICATE
    assert duplicate.delivered_at == receipt.delivered_at
    by_dedupe = backend.deliver(_message(message_id='message-b'))
    assert by_dedupe.status is OutboxDeliveryStatus.DUPLICATE
    assert backend.get_record(tenant_id='tenant-a', message_id='message-a').payload['value'] == 1
    assert backend.get_record(tenant_id='tenant-b', message_id='message-a') is None
    assert backend.get_receipt(tenant_id='tenant-a', message_id='message-a') == receipt
    assert backend.get_receipt(tenant_id='tenant-a', message_id='missing') is None

    with pytest.raises(OutboxDeliveryConflict, match='topic drift'):
        backend.deliver(_message(message_id='message-a', topic='other'))
    with pytest.raises(OutboxDeliveryConflict, match='payload drift'):
        backend.deliver(_message(message_id='message-a', payload={'value': 2}))
    with pytest.raises(OutboxDeliveryConflict, match='topic drift'):
        backend.deliver(_message(message_id='message-c', topic='other'))
    with pytest.raises(OutboxDeliveryConflict, match='payload drift'):
        backend.deliver(_message(message_id='message-c', payload={'value': 2}))

    tenant_b = _message(tenant_id='tenant-b')
    assert backend.deliver(tenant_b).status is OutboxDeliveryStatus.DELIVERED
    assert len(backend.list_records(tenant_id='tenant-a')) == 1
    assert len(backend.list_records(tenant_id='tenant-b')) == 1
    assert backend.list_records(tenant_id='tenant-a', topic='missing') == ()
    assert backend.list_records(tenant_id='tenant-a', limit=0) == ()


def test_explicit_digest_and_row_tuple_decoding(tmp_path: Path) -> None:
    backend = SQLiteOutboxBackend(tmp_path/'digest.sqlite3')
    message = _message(payload_digest='explicit')
    assert backend.deliver(message).payload_digest == 'explicit'
    row = (
        'tenant-a','message-x','topic-x','dedupe-x',json.dumps({'value': 3}),None,NOW.isoformat(),None,
        backend.backend_name,json.dumps({'x': 1})
    )
    record = backend._row_to_record(row)
    assert record.receipt.payload_digest is None
    assert record.receipt.external_id is None
    assert record.payload == {'value': 3}


def test_semantic_match_allows_legacy_blank_digest_but_rejects_drift(tmp_path: Path) -> None:
    backend = SQLiteOutboxBackend(tmp_path/'legacy.sqlite3')
    message = _message()
    backend.deliver(message)
    with backend._connect() as conn:
        conn.execute("UPDATE outbox_delivery SET payload_digest='' WHERE tenant_id=? AND message_id=?", ('tenant-a','message-a'))
        conn.commit()
    assert backend.deliver(message).status is OutboxDeliveryStatus.DUPLICATE


def test_health_parent_existence_and_empty_records(tmp_path: Path) -> None:
    path = tmp_path/'nested'/'outbox.sqlite3'
    backend = SQLiteOutboxBackend(path)
    assert backend.healthcheck().healthy
    assert backend.list_records(tenant_id='tenant-a', topic=None, limit=5) == ()

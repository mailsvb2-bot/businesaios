from __future__ import annotations

from reliability.outbox_backend import OutboxDeliveryConflict, OutboxDeliveryStatus
from reliability.outbox_file_backend import FileOutboxBackend
from reliability.outbox_sqlite_backend import SQLiteOutboxBackend
from reliability.outbox_store import OutboxMessage


def _message(*, message_id: str = 'msg-1', dedupe_key: str = 'd-1', payload: dict | None = None, topic: str = 'effects') -> OutboxMessage:
    return OutboxMessage(
        tenant_id='tenant-a',
        message_id=message_id,
        topic=topic,
        dedupe_key=dedupe_key,
        payload={'ok': True} if payload is None else payload,
    )


def test_file_outbox_backend_duplicate_and_conflict(tmp_path) -> None:
    backend = FileOutboxBackend(tmp_path / 'outbox-files')

    first = backend.deliver(_message())
    assert first.status is OutboxDeliveryStatus.DELIVERED

    duplicate = backend.deliver(_message())
    assert duplicate.status is OutboxDeliveryStatus.DUPLICATE

    try:
        backend.deliver(_message(payload={'ok': False}))
    except OutboxDeliveryConflict:
        pass
    else:
        raise AssertionError('expected file backend delivery conflict')



def test_sqlite_outbox_backend_duplicate_by_dedupe_key(tmp_path) -> None:
    backend = SQLiteOutboxBackend(tmp_path / 'outbox.sqlite3')

    first = backend.deliver(_message(message_id='msg-1', dedupe_key='same-dedupe'))
    assert first.status is OutboxDeliveryStatus.DELIVERED

    duplicate = backend.deliver(_message(message_id='msg-2', dedupe_key='same-dedupe'))
    assert duplicate.status is OutboxDeliveryStatus.DUPLICATE



def test_sqlite_outbox_backend_conflict_on_payload_drift(tmp_path) -> None:
    backend = SQLiteOutboxBackend(tmp_path / 'outbox.sqlite3')
    backend.deliver(_message(message_id='msg-1', dedupe_key='same-dedupe', payload={'value': 1}))

    try:
        backend.deliver(_message(message_id='msg-2', dedupe_key='same-dedupe', payload={'value': 2}))
    except OutboxDeliveryConflict:
        pass
    else:
        raise AssertionError('expected sqlite backend delivery conflict')

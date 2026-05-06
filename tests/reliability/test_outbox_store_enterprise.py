from __future__ import annotations

import pytest

from reliability.outbox_store import InMemoryOutboxStore, OutboxMessage, OutboxStoreConflict


def test_outbox_store_rejects_payload_drift_for_same_dedupe_key() -> None:
    store = InMemoryOutboxStore()
    store.enqueue(OutboxMessage(tenant_id='tenant-a', message_id='m1', topic='effects.email', dedupe_key='d1', payload={'value': 1}))

    with pytest.raises(OutboxStoreConflict):
        store.enqueue(OutboxMessage(tenant_id='tenant-a', message_id='m2', topic='effects.email', dedupe_key='d1', payload={'value': 2}))


def test_outbox_store_rejects_topic_drift_for_same_message_id() -> None:
    store = InMemoryOutboxStore()
    store.enqueue(OutboxMessage(tenant_id='tenant-a', message_id='m1', topic='effects.email', dedupe_key='d1', payload={'value': 1}))

    with pytest.raises(OutboxStoreConflict):
        store.enqueue(OutboxMessage(tenant_id='tenant-a', message_id='m1', topic='effects.sms', dedupe_key='d2', payload={'value': 1}))

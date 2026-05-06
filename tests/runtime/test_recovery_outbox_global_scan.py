from __future__ import annotations

from dataclasses import dataclass

from reliability.outbox_store import InMemoryOutboxStore, OutboxMessage
from runtime.recovery import _iter_recoverable_items


@dataclass
class _Decision:
    decision_id: str


def test_recovery_iterates_claimable_items_across_tenants_for_reliability_outbox() -> None:
    outbox = InMemoryOutboxStore()
    outbox.enqueue(OutboxMessage(tenant_id='tenant-a', message_id='m1', topic='effects', dedupe_key='d1', payload={'ok': True}))
    outbox.enqueue(OutboxMessage(tenant_id='tenant-b', message_id='m2', topic='effects', dedupe_key='d2', payload={'ok': True}))

    items = list(_iter_recoverable_items(outbox=outbox, limit=10))
    assert {item['tenant_id'] for item in items} == {'tenant-a', 'tenant-b'}
    assert {item['message_id'] for item in items} == {'m1', 'm2'}

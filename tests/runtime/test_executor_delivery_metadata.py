from __future__ import annotations

from dataclasses import dataclass

from reliability.outbox_store import InMemoryOutboxStore
from runtime.execution.executor_commit import (
    build_delivery_metadata,
    claim_or_skip,
    enqueue_once,
    get_delivery_info,
    mark_delivered,
)


@dataclass
class _Decision:
    decision_id: str = 'dec-1'
    correlation_id: str = 'corr-1'
    action: str = 'send_message@v1'
    payload: dict | None = None


def test_executor_commit_persists_delivery_metadata_for_reliability_outbox() -> None:
    outbox = InMemoryOutboxStore()
    decision = _Decision(payload={'tenant_id': 'tenant-a', 'chat_id': '1', 'text': 'hello'})
    enqueue_once(outbox, decision=decision)
    assert claim_or_skip(outbox, decision_id='dec-1', tenant_id='tenant-a', owner_id='runtime-executor')
    metadata = build_delivery_metadata(decision=decision, mode='delivered', owner_id='runtime-executor')
    mark_delivered(
        outbox,
        decision_id='dec-1',
        tenant_id='tenant-a',
        owner_id='runtime-executor',
        backend_name='runtime_executor',
        external_id='dec-1',
        payload_digest=metadata['payload_digest'],
        metadata=metadata,
    )

    info = get_delivery_info(outbox, decision_id='dec-1', tenant_id='tenant-a')
    assert info is not None
    assert info['delivery_metadata']['owner_id'] == 'runtime-executor'
    assert info['delivery_metadata']['effect_kind'] == 'runtime_effect'
    assert info['delivery_metadata']['action'] == 'send_message@v1'

from __future__ import annotations

from datetime import timedelta

from reliability.outbox_store import InMemoryOutboxStore, OutboxMessage, OutboxState, OutboxStoreConflict, utc_now


def _message(*, now=None) -> OutboxMessage:
    if now is None:
        now = utc_now()
    return OutboxMessage(
        tenant_id="tenant-1",
        message_id="msg-1",
        topic="effects",
        dedupe_key="dedupe-1",
        payload={"ok": True},
        created_at=now,
        updated_at=now,
        available_at=now,
    )


def test_outbox_reclaims_expired_delivery_claim() -> None:
    store = InMemoryOutboxStore()
    now = utc_now()
    store.enqueue(_message(now=now))
    claimed = store.claim(tenant_id="tenant-1", message_id="msg-1", owner_id="worker-a", claim_ttl_seconds=1, now=now)
    assert claimed is not None
    assert claimed.state is OutboxState.DELIVERING

    later = now + timedelta(seconds=2)
    claimable = store.list_claimable(tenant_id="tenant-1", now=later)
    assert [m.message_id for m in claimable] == ["msg-1"]

    stolen = store.claim(tenant_id="tenant-1", message_id="msg-1", owner_id="worker-b", claim_ttl_seconds=30, now=later)
    assert stolen is not None
    assert stolen.claim_owner_id == "worker-b"
    assert stolen.delivery_attempts == 2


def test_outbox_dedupe_returns_existing_message_for_semantic_duplicate() -> None:
    store = InMemoryOutboxStore()
    first = store.enqueue(_message())
    second = store.enqueue(
        OutboxMessage(
            tenant_id="tenant-1",
            message_id="msg-2",
            topic="effects",
            dedupe_key="dedupe-1",
            payload={"ok": True},
        )
    )
    assert first.message_id == second.message_id == "msg-1"


def test_outbox_dedupe_rejects_payload_drift() -> None:
    store = InMemoryOutboxStore()
    store.enqueue(_message())
    try:
        store.enqueue(
            OutboxMessage(
                tenant_id="tenant-1",
                message_id="msg-2",
                topic="effects",
                dedupe_key="dedupe-1",
                payload={"ok": False},
            )
        )
    except OutboxStoreConflict:
        pass
    else:
        raise AssertionError("expected OutboxStoreConflict")

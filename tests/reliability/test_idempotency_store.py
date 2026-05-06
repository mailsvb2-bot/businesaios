from __future__ import annotations

from datetime import timedelta

from reliability.idempotency_contract import IdempotencyKey, IdempotencyResolution, utc_now
from reliability.idempotency_store import InMemoryIdempotencyStore


def _key(scope_hash: str = "scope-1") -> IdempotencyKey:
    return IdempotencyKey(
        tenant_id="tenant-1",
        namespace="runtime",
        operation="execute",
        key="run-1",
        scope_hash=scope_hash,
    )


def test_idempotency_replays_completed_result() -> None:
    store = InMemoryIdempotencyStore()
    decision = store.reserve(key=_key(), owner_id="owner-a")
    assert decision.resolution is IdempotencyResolution.ACCEPTED
    store.mark_completed(key=_key(), owner_id="owner-a", result_ref="result://1", result_digest="abc")

    replay = store.reserve(key=_key(), owner_id="owner-b")
    assert replay.resolution is IdempotencyResolution.REPLAY_COMPLETED
    assert replay.replay_result_ref == "result://1"
    assert replay.replay_result_digest == "abc"


def test_idempotency_rejects_scope_mismatch() -> None:
    store = InMemoryIdempotencyStore()
    store.reserve(key=_key("scope-1"), owner_id="owner-a")
    mismatch = store.reserve(key=_key("scope-2"), owner_id="owner-b")
    assert mismatch.resolution is IdempotencyResolution.REJECTED_SCOPE_MISMATCH


def test_idempotency_allows_steal_after_lease_expiry() -> None:
    store = InMemoryIdempotencyStore()
    now = utc_now()
    store.reserve(key=_key(), owner_id="owner-a", lease_ttl_seconds=1, now=now)
    later = now + timedelta(seconds=2)
    decision = store.reserve(key=_key(), owner_id="owner-b", lease_ttl_seconds=30, now=later)
    assert decision.resolution is IdempotencyResolution.ACCEPTED
    assert decision.record.owner_id == "owner-b"
    assert decision.record.attempt_count == 2

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

import reliability.idempotency_store as module
from reliability.idempotency_contract import IdempotencyResolution, IdempotencyState
from reliability.idempotency_store import InMemoryIdempotencyStore
from tests.unit.reliability.idempotency_wave40_support import NOW, key

def test_helpers_and_in_memory_full_lifecycle():
    assert module._merge_metadata(None, None) == {}
    assert module._merge_metadata({"a": 1}, {"b": 2}) == {"a": 1, "b": 2}
    for value in ("", "   ", None):
        with pytest.raises(ValueError, match="owner_id"):
            module._owner_id(value)
    assert module._owner_id(" owner-a ") == "owner-a"
    for value in (0, -1):
        with pytest.raises(ValueError, match="lease_ttl_seconds"):
            module._positive_ttl(value)
    assert module._positive_ttl("2") == 2
    with pytest.raises(ValueError, match="timezone-aware"):
        module._aware_moment(datetime(2026, 1, 1))
    assert module._aware_moment(NOW) is NOW

    store = InMemoryIdempotencyStore()
    with pytest.raises(ValueError, match="owner_id"):
        store.reserve(key=key(), owner_id="")
    with pytest.raises(ValueError, match="lease_ttl_seconds"):
        store.reserve(key=key(), owner_id="owner-a", lease_ttl_seconds=0)
    with pytest.raises(ValueError, match="timezone-aware"):
        store.reserve(key=key(), owner_id="owner-a", now=datetime(2026, 1, 1))

    accepted = store.reserve(
        key=key(),
        owner_id=" owner-a ",
        lease_ttl_seconds=10,
        now=NOW,
        metadata_patch={"phase": "reserve"},
    )
    assert accepted.resolution is IdempotencyResolution.ACCEPTED
    assert accepted.record.owner_id == "owner-a"
    assert accepted.record.attempt_count == 1
    assert accepted.record.metadata == {"phase": "reserve"}
    assert store.get(key=key()) == accepted.record
    with pytest.raises(TypeError):
        accepted.record.metadata["mutated"] = True
    assert store.get(key=key()).metadata == {"phase": "reserve"}

    mismatch = store.reserve(
        key=key(scope="scope-b"), owner_id="owner-b", now=NOW
    )
    assert mismatch.resolution is IdempotencyResolution.REJECTED_SCOPE_MISMATCH
    progress = store.reserve(key=key(), owner_id="owner-b", now=NOW)
    assert progress.resolution is IdempotencyResolution.REJECTED_IN_PROGRESS

    with pytest.raises(KeyError, match="not found"):
        store.renew_lease(key=key("missing"), owner_id="owner-a", now=NOW)
    with pytest.raises(PermissionError, match="owner mismatch"):
        store.renew_lease(key=key(), owner_id="owner-b", now=NOW)
    with pytest.raises(ValueError, match="lease_ttl_seconds"):
        store.renew_lease(
            key=key(), owner_id="owner-a", lease_ttl_seconds=0, now=NOW
        )

    renewed = store.renew_lease(
        key=key(),
        owner_id="owner-a",
        lease_ttl_seconds=20,
        now=NOW + timedelta(seconds=1),
        metadata_patch={"phase": "renew"},
    )
    assert renewed.attempt_count == 1
    assert renewed.lease_expires_at == NOW + timedelta(seconds=21)
    assert renewed.metadata == {"phase": "renew"}

    completed = store.mark_completed(
        key=key(),
        owner_id="owner-a",
        result_ref="result://1",
        result_digest="digest",
        now=NOW + timedelta(seconds=2),
        metadata_patch={"done": True},
    )
    assert completed.state is IdempotencyState.COMPLETED
    replay = store.reserve(
        key=key(), owner_id="owner-b", now=NOW + timedelta(seconds=3)
    )
    assert replay.resolution is IdempotencyResolution.REPLAY_COMPLETED
    assert replay.replay_result_ref == "result://1"
    assert replay.replay_result_digest == "digest"
    with pytest.raises(RuntimeError, match="terminal"):
        store.mark_failed(
            key=key(), owner_id="owner-a", now=NOW + timedelta(seconds=3)
        )

    failed_key = key("failed")
    store.reserve(key=failed_key, owner_id="owner-a", now=NOW)
    failed = store.mark_failed(
        key=failed_key,
        owner_id="owner-a",
        reason="boom",
        now=NOW + timedelta(seconds=1),
    )
    assert failed.state is IdempotencyState.FAILED
    rejected = store.reserve(
        key=failed_key, owner_id="owner-b", now=NOW + timedelta(seconds=2)
    )
    assert rejected.resolution is IdempotencyResolution.REJECTED_TERMINAL_FAILED


def test_expiry_fences_stale_owner_and_allows_one_steal():
    store = InMemoryIdempotencyStore()
    expiring = key("expiring")
    live = key("live")
    store.reserve(
        key=expiring, owner_id="owner-a", lease_ttl_seconds=1, now=NOW
    )
    store.reserve(key=live, owner_id="owner-a", lease_ttl_seconds=30, now=NOW)

    with pytest.raises(PermissionError, match="lease is not active"):
        store.mark_completed(
            key=expiring,
            owner_id="owner-a",
            now=NOW + timedelta(seconds=2),
        )
    assert store.expire_stale(now=NOW + timedelta(seconds=2)) == 1
    assert store.expire_stale(now=NOW + timedelta(seconds=2)) == 0
    with pytest.raises(PermissionError, match="lease is not active"):
        store.renew_lease(
            key=expiring,
            owner_id="owner-a",
            now=NOW + timedelta(seconds=2),
        )

    stolen = store.reserve(
        key=expiring,
        owner_id="owner-b",
        lease_ttl_seconds=10,
        now=NOW + timedelta(seconds=3),
        metadata_patch={"stolen": True},
    )
    assert stolen.resolution is IdempotencyResolution.ACCEPTED
    assert stolen.record.owner_id == "owner-b"
    assert stolen.record.attempt_count == 2
    assert stolen.record.metadata["stolen"] is True
    assert store.expire_stale(now=NOW + timedelta(seconds=4)) == 0



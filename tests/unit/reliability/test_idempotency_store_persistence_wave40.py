from __future__ import annotations

import json
import os
import sys
from datetime import timedelta
from pathlib import Path
from threading import Barrier, Thread
from types import SimpleNamespace

import pytest

import reliability.idempotency_store as module
from reliability.idempotency_contract import IdempotencyResolution, IdempotencyState
from reliability.idempotency_store import JsonlIdempotencyStore
from tests.unit.reliability.idempotency_wave40_support import NOW, key

def test_jsonl_lifecycle_noop_writes_and_cross_instance_visibility(tmp_path: Path):
    path = tmp_path / "store.jsonl"
    first = JsonlIdempotencyStore(path)
    second = JsonlIdempotencyStore(path)
    accepted = first.reserve(
        key=key(), owner_id="owner-a", lease_ttl_seconds=30, now=NOW
    )
    assert accepted.resolution is IdempotencyResolution.ACCEPTED
    initial = path.read_bytes()

    rejected = second.reserve(key=key(), owner_id="owner-b", now=NOW)
    assert rejected.resolution is IdempotencyResolution.REJECTED_IN_PROGRESS
    assert path.read_bytes() == initial
    mismatch = second.reserve(
        key=key(scope="scope-b"), owner_id="owner-b", now=NOW
    )
    assert mismatch.resolution is IdempotencyResolution.REJECTED_SCOPE_MISMATCH
    assert path.read_bytes() == initial

    renewed = second.renew_lease(
        key=key(), owner_id="owner-a", lease_ttl_seconds=40, now=NOW
    )
    assert renewed.lease_expires_at == NOW + timedelta(seconds=40)
    completed = first.mark_completed(
        key=key(),
        owner_id="owner-a",
        result_ref="result://done",
        now=NOW + timedelta(seconds=1),
    )
    assert completed.state is IdempotencyState.COMPLETED
    reopened = JsonlIdempotencyStore(path)
    assert reopened.get(key=key()) == completed

    failed_key = key("failed")
    first.reserve(key=failed_key, owner_id="owner-a", now=NOW)
    failed = second.mark_failed(
        key=failed_key,
        owner_id="owner-a",
        reason="boom",
        now=NOW + timedelta(seconds=1),
    )
    assert JsonlIdempotencyStore(path).get(key=failed_key) == failed


def test_two_instances_race_has_one_reservation_winner(tmp_path: Path):
    path = tmp_path / "race.jsonl"
    stores = [JsonlIdempotencyStore(path), JsonlIdempotencyStore(path)]
    start = Barrier(3)
    decisions = []
    errors = []

    def reserve(store, owner):
        try:
            start.wait(timeout=5)
            decisions.append(
                store.reserve(key=key(), owner_id=owner, now=NOW).resolution
            )
        except BaseException as exc:  # pragma: no cover - diagnostic only
            errors.append(exc)

    threads = [
        Thread(target=reserve, args=(stores[0], "owner-a")),
        Thread(target=reserve, args=(stores[1], "owner-b")),
    ]
    for thread in threads:
        thread.start()
    start.wait(timeout=5)
    for thread in threads:
        thread.join(timeout=5)

    assert not errors
    assert not any(thread.is_alive() for thread in threads)
    assert sorted(decision.value for decision in decisions) == [
        "accepted",
        "rejected_in_progress",
    ]
    persisted = JsonlIdempotencyStore(path).get(key=key())
    assert persisted is not None
    assert persisted.attempt_count == 1


def test_persistence_failure_recovers_durable_truth(tmp_path: Path, monkeypatch):
    path = tmp_path / "failure.jsonl"
    store = JsonlIdempotencyStore(path)

    def fail_before_write(_records):
        raise OSError("disk full")

    monkeypatch.setattr(store, "_append_records_unlocked", fail_before_write)
    with pytest.raises(OSError, match="disk full"):
        store.reserve(key=key(), owner_id="owner-a", now=NOW)
    assert store.get(key=key()) is None

    monkeypatch.undo()
    store = JsonlIdempotencyStore(path)
    real_write = os.write
    calls = 0

    def partial_write(fd, data):
        nonlocal calls
        calls += 1
        return real_write(fd, bytes(data[:7]))

    monkeypatch.setattr(module.os, "write", partial_write)
    accepted = store.reserve(key=key(), owner_id="owner-a", now=NOW)
    assert accepted.resolution is IdempotencyResolution.ACCEPTED
    assert calls > 1
    assert JsonlIdempotencyStore(path).get(key=key()) is not None

    monkeypatch.undo()
    no_progress = JsonlIdempotencyStore(tmp_path / "no-progress.jsonl")
    monkeypatch.setattr(module.os, "write", lambda _fd, _data: 0)
    with pytest.raises(OSError, match="no progress"):
        no_progress.reserve(key=key(), owner_id="owner-a", now=NOW)
    assert no_progress.get(key=key()) is None


def test_expire_stale_is_one_committed_multi_record_transaction(tmp_path: Path):
    path = tmp_path / "expire.jsonl"
    store = JsonlIdempotencyStore(path)
    for name in ("a", "b"):
        store.reserve(
            key=key(name),
            owner_id="owner-a",
            lease_ttl_seconds=1,
            now=NOW,
        )
    store.reserve(
        key=key("live"),
        owner_id="owner-a",
        lease_ttl_seconds=30,
        now=NOW,
    )
    assert store.expire_stale(
        now=NOW + timedelta(seconds=2), metadata_patch={"swept": True}
    ) == 2
    rows = [json.loads(line) for line in path.read_text().splitlines()]
    last_begin = max(
        index
        for index, row in enumerate(rows)
        if row.get(module._JOURNAL_FIELD) == "begin"
    )
    assert rows[last_begin]["count"] == 2
    reopened = JsonlIdempotencyStore(path)
    assert reopened.get(key=key("a")).state is IdempotencyState.EXPIRED
    assert reopened.get(key=key("b")).metadata["swept"] is True
    assert reopened.get(key=key("live")).state is IdempotencyState.IN_PROGRESS


def test_windows_file_lock_adapter_branch(tmp_path: Path, monkeypatch):
    path = tmp_path / "windows.jsonl"
    store = JsonlIdempotencyStore(path)
    calls = []

    fake = SimpleNamespace(
        LK_LOCK=1,
        LK_UNLCK=2,
        locking=lambda fd, mode, count: calls.append((fd, mode, count)),
    )
    monkeypatch.setitem(sys.modules, "msvcrt", fake)
    monkeypatch.setattr(module.os, "name", "nt")
    store._lock_path.write_bytes(b"")
    with store._exclusive_file_lock():
        assert store._lock_path.read_bytes() == b"\0"
    with store._exclusive_file_lock():
        pass
    assert [call[1] for call in calls] == [
        fake.LK_LOCK,
        fake.LK_UNLCK,
        fake.LK_LOCK,
        fake.LK_UNLCK,
    ]

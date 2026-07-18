from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from core.observability import perf_watchdog
from reliability import outbox_file_backend as file_module
from reliability.outbox_backend import (
    OutboxBackendHealth,
    OutboxBackendMode,
    OutboxDeliveryConflict,
    OutboxDeliveryError,
    OutboxDeliveryReceipt,
    OutboxDeliveryRecord,
    OutboxDeliveryStatus,
)
from reliability.outbox_file_backend import FileOutboxBackend, _json_default, _payload_digest, _safe_segment
from reliability.outbox_store import (
    InMemoryOutboxStore,
    OutboxMessage,
    OutboxState,
    OutboxStoreConflict,
    canonical_payload_digest,
)


def _message(*, message_id: str = "m1", dedupe: str = "d1", payload=None, **changes) -> OutboxMessage:
    now = datetime.now(UTC)
    values = dict(
        tenant_id="tenant",
        message_id=message_id,
        topic="events",
        dedupe_key=dedupe,
        payload={"x": 1} if payload is None else payload,
        created_at=now,
        updated_at=now,
        available_at=now,
    )
    values.update(changes)
    return OutboxMessage(**values)


def test_outbox_contract_validation_and_in_memory_state_machine() -> None:
    now = datetime.now(UTC)
    assert len(canonical_payload_digest({"at": now, "x": 1})) == 64
    with pytest.raises(TypeError):
        canonical_payload_digest({"bad": object()})

    base = _message(available_at=now - timedelta(seconds=1))
    base.validate()
    for field in ("message_id", "topic", "dedupe_key"):
        with pytest.raises(ValueError):
            _message(**{field: ""}).validate()
    with pytest.raises(ValueError, match="timezone-aware"):
        _message(created_at=datetime.now()).validate()
    with pytest.raises(ValueError, match="claim_expires_at"):
        _message(claim_expires_at=datetime.now()).validate()
    with pytest.raises(ValueError, match="delivered_at"):
        _message(delivered_at=datetime.now()).validate()
    with pytest.raises(ValueError, match="delivery_attempts"):
        _message(delivery_attempts=-1).validate()
    with pytest.raises(ValueError, match="payload_digest"):
        _message(payload_digest=" ").validate()
    with pytest.raises(ValueError, match="mapping"):
        _message(delivery_metadata=[]).validate()

    assert base.resolved_payload_digest == canonical_payload_digest(base.payload)
    assert base.semantically_matches(_message(message_id="other"))
    assert not base.semantically_matches(_message(payload={"x": 2}))
    assert not base.is_claim_expired(now=now)
    assert base.is_claimable(now=now)
    assert not _message(available_at=now + timedelta(seconds=10)).is_claimable(now=now)
    assert not _message(state=OutboxState.DEAD).is_claimable(now=now)
    expired_claim = _message(
        state=OutboxState.DELIVERING,
        available_at=now - timedelta(seconds=2),
        claim_expires_at=now - timedelta(seconds=1),
    )
    assert expired_claim.is_claim_expired(now=now) and expired_claim.is_claimable(now=now)

    delivered = base.with_delivery_receipt(
        backend_name="backend",
        external_id="external",
        delivered_at=now,
        metadata={"ok": True},
    )
    assert delivered.state is OutboxState.DELIVERED and delivered.delivery_metadata == {"ok": True}

    store = InMemoryOutboxStore()
    first = store.enqueue(base)
    assert store.enqueue(_message()) == first
    assert store.get(tenant_id="tenant", message_id="m1") == first
    assert store.get_by_dedupe_key(tenant_id="tenant", dedupe_key="d1") == first
    assert store.get_by_dedupe_key(tenant_id="tenant", dedupe_key="none") is None
    assert store.list_claimable(tenant_id="tenant", limit=0, now=now) == (first,)
    assert store.list_claimable_all(limit=0, now=now) == (first,)

    with pytest.raises(OutboxStoreConflict, match="payload drift"):
        store.enqueue(_message(message_id="m2", dedupe="d1", payload={"x": 2}))
    with pytest.raises(OutboxStoreConflict, match="topic drift"):
        store.enqueue(_message(message_id="m1", dedupe="other", topic="other"))
    with pytest.raises(ValueError, match="owner_id"):
        store.claim(tenant_id="tenant", message_id="m1", owner_id="")
    claimed = store.claim(tenant_id="tenant", message_id="m1", owner_id="worker", claim_ttl_seconds=0, now=now)
    assert claimed.state is OutboxState.DELIVERING and claimed.delivery_attempts == 1
    assert store.claim(tenant_id="tenant", message_id="m1", owner_id="other", now=now) is None
    with pytest.raises(PermissionError):
        store.mark_delivered(tenant_id="tenant", message_id="m1", owner_id="wrong")
    retry = store.schedule_retry(
        tenant_id="tenant",
        message_id="m1",
        owner_id="worker",
        delay_seconds=0,
        error="retry",
        now=now,
    )
    assert retry.state is OutboxState.PENDING and retry.last_error == "retry"
    assert store.claim(tenant_id="tenant", message_id="m1", owner_id="worker", now=now) is None
    claimed2 = store.claim(tenant_id="tenant", message_id="m1", owner_id="worker", now=now + timedelta(seconds=1))
    done = store.mark_delivered(
        tenant_id="tenant",
        message_id="m1",
        owner_id="worker",
        now=now + timedelta(seconds=1),
        backend_name="file",
        external_id="x",
        metadata={"delivered": True},
    )
    assert claimed2 is not None and done.state is OutboxState.DELIVERED
    with pytest.raises(PermissionError):
        store.move_to_dead_letter(tenant_id="tenant", message_id="m1", owner_id="worker", error="dead")
    store._messages[("tenant", "m1")] = replace(done, claim_owner_id="worker")
    with pytest.raises(RuntimeError):
        store.move_to_dead_letter(tenant_id="tenant", message_id="m1", owner_id="worker", error="dead")
    with pytest.raises(KeyError):
        store.claim(tenant_id="tenant", message_id="missing", owner_id="worker")

    second = store.enqueue(_message(message_id="m2", dedupe="d2"))
    assert store.claim(tenant_id="tenant", message_id=second.message_id, owner_id="worker") is not None
    dead = store.move_to_dead_letter(tenant_id="tenant", message_id="m2", owner_id="worker", error="fatal")
    assert dead.state is OutboxState.DEAD


def test_file_outbox_backend_idempotency_drift_and_serialization(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(file_module, "_fsync_directory", lambda _path: None)
    assert _safe_segment("a b/c") == "a_b_c"
    with pytest.raises(ValueError):
        _safe_segment("")
    with pytest.raises(ValueError):
        _safe_segment("...")
    assert _json_default(datetime(2026, 1, 1, tzinfo=UTC)).startswith("2026")
    with pytest.raises(TypeError):
        _json_default(object())
    assert _payload_digest({"x": 1}) == _payload_digest({"x": 1})

    backend = FileOutboxBackend(tmp_path / "outbox")
    health = backend.healthcheck()
    assert health.healthy and health.mode is OutboxBackendMode.DURABLE
    message = _message(payload={"when": datetime(2026, 1, 1, tzinfo=UTC), "x": 1})
    receipt = backend.deliver(message)
    assert receipt.status is OutboxDeliveryStatus.DELIVERED
    assert backend.get_receipt(tenant_id="tenant", message_id="m1") == receipt
    record = backend.get_record(tenant_id="tenant", message_id="m1")
    assert record.payload["x"] == 1
    duplicate = backend.deliver(message)
    assert duplicate.status is OutboxDeliveryStatus.DUPLICATE
    assert len(backend.list_records(tenant_id="tenant")) == 1
    assert len(backend.list_records(tenant_id="tenant", topic="events", limit=0)) == 1
    assert backend.list_records(tenant_id="other") == ()
    assert backend.get_record(tenant_id="tenant", message_id="none") is None
    with pytest.raises(OutboxDeliveryConflict) as conflict:
        backend.deliver(_message(payload={"x": 999}))
    assert not conflict.value.retryable and conflict.value.code == "delivery_conflict"

    for item in (
        OutboxBackendHealth("", True),
        OutboxBackendHealth("x", True, checked_at=datetime.now()),
    ):
        with pytest.raises(ValueError):
            item.validate()
    for item in (
        OutboxDeliveryReceipt("", "m", "b", OutboxDeliveryStatus.DELIVERED),
        OutboxDeliveryReceipt("t", "", "b", OutboxDeliveryStatus.DELIVERED),
        OutboxDeliveryReceipt("t", "m", "", OutboxDeliveryStatus.DELIVERED),
        OutboxDeliveryReceipt("t", "m", "b", OutboxDeliveryStatus.DELIVERED, delivered_at=datetime.now()),
    ):
        with pytest.raises(ValueError):
            item.validate()
    with pytest.raises(ValueError, match="topic"):
        OutboxDeliveryRecord(receipt, "", "d").validate()
    with pytest.raises(ValueError, match="dedupe"):
        OutboxDeliveryRecord(receipt, "t", "").validate()
    error = OutboxDeliveryError("x", retryable=False, code="c", details={"x": 1})
    assert not error.retryable and error.code == "c" and error.details == {"x": 1}


def test_perf_watchdog_tracks_summarizes_and_emits(monkeypatch: pytest.MonkeyPatch) -> None:
    perf_watchdog.ROLLING_CK_TO_BTN.clear()
    perf_watchdog.ROLLING_BTN_TOTALS.clear()
    perf_watchdog.RECENT_SLA_BREACHES.clear()
    monkeypatch.setattr(perf_watchdog, "LAST_WATCHDOG_MS", 0)
    monkeypatch.setattr(perf_watchdog, "LAST_EMITTED_OFFENDERS", "")
    monkeypatch.setattr(perf_watchdog, "sla_budget_ms", lambda: 100)
    monkeypatch.setattr(
        perf_watchdog,
        "env_int",
        lambda name, default, lo, hi: 10 if "INTERVAL" in name else 2,
    )
    monkeypatch.setattr(perf_watchdog.time, "time", lambda: 100.0)

    perf_watchdog.rolling_track("router", None, {}, 1)
    perf_watchdog.rolling_track("router", "c1", {"button_key": "buy"}, 1)
    perf_watchdog.rolling_track("other", "c1", {}, 1)
    perf_watchdog.rolling_track("execute_total", "c1", {}, -5)
    perf_watchdog.rolling_track("execute_total", "c1", {}, 200)
    perf_watchdog.rolling_track("execute_total", "unknown", {}, 50)
    assert perf_watchdog.recent_sla_breaches(limit=0) == []
    assert perf_watchdog.recent_sla_breaches(limit="bad") == []
    summary = perf_watchdog.rolling_latency_summary(top_n="bad")
    assert summary["budget_ms"] == 100 and summary["top_buttons"][0]["button"] == "buy"

    class Log:
        def __init__(self):
            self.events = []

        def emit(self, **payload):
            self.events.append(payload)

    log = Log()
    perf_watchdog.watchdog_tick(log)
    assert log.events and log.events[0]["event_type"] == "latency_sla_breached"
    assert perf_watchdog.recent_sla_breaches(limit=3)[0]["offenders"][0]["button"] == "buy"
    perf_watchdog.watchdog_tick(log)
    assert len(log.events) == 1

    monkeypatch.setattr(perf_watchdog.time, "time", lambda: 200.0)
    perf_watchdog.watchdog_tick(None)
    perf_watchdog.watchdog_tick(object())

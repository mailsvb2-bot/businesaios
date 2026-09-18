from __future__ import annotations

from types import SimpleNamespace

import pytest

from contracts.event_store import BusinessFactV1, canonical_business_event_contract
from contracts.messaging_event_identity import MessageDirection, MessageIdentity
from reliability.idempotency_store import InMemoryIdempotencyStore
from runtime.messaging.message_registry import (
    MESSAGE_ARCHIVED,
    MESSAGE_RECORDED,
    MessageHistoryInvariantViolation,
    MessageLifecycleStatus,
    MessageProjector,
    MessageRegistry,
)
from runtime.messaging.outbound_message import OutboundMessage
from runtime.platform.event_store.memory_event_store import MemoryEventStore


def _registry(events=None):
    store = events or MemoryEventStore()
    return MessageRegistry(
        event_store=store,
        idempotency_store=InMemoryIdempotencyStore(),
    ), store


def _identity(*, message_id="provider-1", direction=MessageDirection.INBOUND):
    return MessageIdentity(
        message_id=message_id,
        tenant_id="tenant-a",
        business_id="business-a",
        channel="telegram",
        direction=direction,
        correlation_id="corr-a",
        transport_message_id=message_id if direction is MessageDirection.INBOUND else "",
    )


def test_message_record_is_deterministic_pii_free_and_idempotent() -> None:
    registry, events = _registry()
    first = registry.record(
        identity=_identity(), customer_id="customer-a", conversation_id="conversation-a",
        occurred_at_ms=100,
    )
    replay = registry.record(
        identity=_identity(), customer_id="customer-a", conversation_id="conversation-a",
        occurred_at_ms=200,
    )
    assert replay == first
    assert first.message_id.startswith("message:")
    assert first.lifecycle_status is MessageLifecycleStatus.RECORDED
    assert len(list(events.iter_events(tenant_id="tenant-a", start_ms=0))) == 1
    serialized = repr(list(events))
    for forbidden in ("provider-1", "corr-a", "hello", "user-1", "email", "phone"):
        assert forbidden not in serialized


def test_message_identity_relations_are_immutable() -> None:
    registry, _ = _registry()
    registry.record(
        identity=_identity(), customer_id="customer-a", conversation_id="conversation-a",
        occurred_at_ms=100,
    )
    with pytest.raises(ValueError, match="identity metadata cannot be rewritten"):
        registry.record(
            identity=_identity(), customer_id="customer-b", conversation_id="conversation-a",
            occurred_at_ms=200,
        )
    with pytest.raises(ValueError, match="requires customer_id"):
        registry.record(
            identity=_identity(message_id="provider-2"), conversation_id="conversation-a",
            occurred_at_ms=200,
        )


def test_message_archive_is_terminal() -> None:
    registry, _ = _registry()
    current = registry.record(identity=_identity(), occurred_at_ms=10)
    archived = registry.archive(
        tenant_id="tenant-a", business_id="business-a", message_id=current.message_id,
        idempotency_key="archive", occurred_at_ms=20,
    )
    assert archived.lifecycle_status is MessageLifecycleStatus.ARCHIVED
    assert archived.archived_at_ms == 20
    replay = registry.record(identity=_identity(), occurred_at_ms=30)
    assert replay.lifecycle_status is MessageLifecycleStatus.ARCHIVED


def test_message_projection_fails_closed_after_archive() -> None:
    registry, events = _registry()
    current = registry.record(identity=_identity(), occurred_at_ms=10)
    registry.archive(
        tenant_id="tenant-a", business_id="business-a", message_id=current.message_id,
        idempotency_key="archive", occurred_at_ms=20,
    )
    events.append_event(BusinessFactV1(
        fact_id="corrupt", tenant_id="tenant-a", business_id="business-a",
        fact_type=MESSAGE_ARCHIVED, entity_id=current.message_id,
        event_time_ms=30, observed_at_ms=30, source="message_registry",
        payload={"schema_version": 1},
    ).as_event())
    with pytest.raises(MessageHistoryInvariantViolation, match="continues after archive"):
        MessageProjector(events).get(
            tenant_id="tenant-a", business_id="business-a", message_id=current.message_id,
        )


def test_message_projection_rejects_noncanonical_source_and_schema() -> None:
    events = MemoryEventStore()
    events.append_event(BusinessFactV1(
        fact_id="bad", tenant_id="tenant-a", business_id="business-a",
        fact_type=MESSAGE_RECORDED, entity_id="message:bad",
        event_time_ms=1, observed_at_ms=1, source="other",
        payload={
            "schema_version": 1, "direction": "inbound", "channel": "telegram",
            "identity_digest": "0" * 64, "customer_id": None, "conversation_id": None,
        },
    ).as_event())
    with pytest.raises(MessageHistoryInvariantViolation, match="noncanonical source"):
        MessageProjector(events).get(
            tenant_id="tenant-a", business_id="business-a", message_id="message:bad",
        )

    schema_events = MemoryEventStore()
    schema_events.append_event(BusinessFactV1(
        fact_id="bad-schema", tenant_id="tenant-a", business_id="business-a",
        fact_type=MESSAGE_RECORDED, entity_id="message:bad-schema",
        event_time_ms=1, observed_at_ms=1, source="message_registry",
        payload={
            "schema_version": 999, "direction": "inbound", "channel": "telegram",
            "identity_digest": "0" * 64, "customer_id": None, "conversation_id": None,
        },
    ).as_event())
    with pytest.raises(MessageHistoryInvariantViolation, match="unsupported schema_version"):
        MessageProjector(schema_events).get(
            tenant_id="tenant-a", business_id="business-a", message_id="message:bad-schema",
        )


def test_message_projection_survives_sqlite_restart(tmp_path) -> None:
    from runtime.platform.event_store.sqlite_event_store import SqliteEventStore

    path = tmp_path / "message.sqlite3"
    with SqliteEventStore(str(path)) as events:
        registry = MessageRegistry(
            event_store=events, idempotency_store=InMemoryIdempotencyStore(),
        )
        created = registry.record(
            identity=_identity(), customer_id="customer-a", conversation_id="conversation-a",
            occurred_at_ms=123,
        )
    with SqliteEventStore(str(path)) as events:
        restored = MessageProjector(events).get(
            tenant_id="tenant-a", business_id="business-a", message_id=created.message_id,
        )
    assert restored.direction is MessageDirection.INBOUND
    assert restored.customer_id == "customer-a"
    assert restored.conversation_id == "conversation-a"
    assert restored.created_at_ms == 123


def _outbound() -> OutboundMessage:
    return OutboundMessage(
        decision_id="decision-1", correlation_id="corr-1", tenant_id="tenant-a",
        business_id="business-a", user_id="user-1", channel="telegram", text="secret text",
    )


def test_business_outbound_is_recorded_before_transport(monkeypatch) -> None:
    from runtime._internal.effects_actions.telegram.messaging_parts import transport

    order: list[str] = []

    class _Registry:
        def record(self, **kwargs):
            order.append("record")
            assert kwargs["identity"].direction is MessageDirection.OUTBOUND
            assert kwargs["business_id"] == "business-a"
            return SimpleNamespace(message_id="message:out")

    effects = SimpleNamespace(message_registry=_Registry())
    monkeypatch.setattr(transport, "telegram_pre_send", lambda *args, **kwargs: None)
    monkeypatch.setattr(transport, "telegram_throttle", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        transport, "telegram_delivery",
        lambda *args, **kwargs: (order.append("send") or True, {"mode": "direct"}),
    )
    ok, _ = transport.build_single_sender(effects)(_outbound())
    assert ok is True
    assert order == ["record", "send"]


def test_business_outbound_registry_failure_blocks_transport(monkeypatch) -> None:
    from runtime._internal.effects_actions.telegram.messaging_parts import transport

    sent: list[str] = []

    class _Registry:
        def record(self, **kwargs):
            raise RuntimeError("message_store_failed")

    effects = SimpleNamespace(message_registry=_Registry())
    monkeypatch.setattr(transport, "telegram_pre_send", lambda *args, **kwargs: sent.append("send"))
    sender = transport.build_single_sender(effects)
    with pytest.raises(RuntimeError, match="message_store_failed"):
        sender(_outbound())
    assert sent == []


def test_legacy_unscoped_outbound_skips_business_message_registry() -> None:
    from runtime._internal.effects_actions.telegram.messaging_parts.transport import _record_business_message

    class _Registry:
        def record(self, **kwargs):
            raise AssertionError("unscoped message must not enter business ontology")

    msg = SimpleNamespace(business_id="", canonical_identity=None)
    assert _record_business_message(SimpleNamespace(message_registry=_Registry()), msg) is None


def test_provider_ingress_records_message_before_processor(monkeypatch) -> None:
    from application.business_autonomy.provider_catalog import provider_map
    from runtime.business_autonomy.provider_inbound_webhook_service import ProviderInboundWebhookService
    from runtime.business_autonomy.provider_webhook_replay_guard import ProviderWebhookReplayGuard
    from runtime.business_autonomy.provider_webhook_runtime import ProviderWebhookRuntime

    order: list[str] = []

    class _Registry:
        def record(self, **kwargs):
            order.append("record")
            assert kwargs["identity"].business_id == "business-a"
            return SimpleNamespace(message_id="message:in")

    class _Processor:
        def process(self, *, handoff):
            assert order == ["record"]
            order.append("process")
            return {"accepted": True, "decision_envelope": {"decision_id": "d1"}}

    monkeypatch.setattr(ProviderWebhookRuntime, "verify", lambda self, **kwargs: True)
    service = ProviderInboundWebhookService(
        webhook_runtime=ProviderWebhookRuntime(None),
        replay_guard=ProviderWebhookReplayGuard(InMemoryIdempotencyStore()),
        inbound_processor=_Processor(), message_registry=_Registry(),
    )
    body = b'{"message":{"from":{"id":42},"text":"hello","message_id":9},"update_id":123}'
    out = service.ingest(
        provider=provider_map()["telegram_bot"], tenant_id="tenant-a", business_id="business-a",
        headers={}, body=body, event_key="evt-message", topic="telegram_update", owner_id="provider_admin",
    )
    assert order == ["record", "process"]
    assert out.metadata["message"] == {"message_id": "message:in"}


def test_provider_ingress_message_persistence_failure_blocks_processor(monkeypatch) -> None:
    from application.business_autonomy.provider_catalog import provider_map
    from runtime.business_autonomy.provider_inbound_webhook_service import ProviderInboundWebhookService
    from runtime.business_autonomy.provider_webhook_replay_guard import ProviderWebhookReplayGuard
    from runtime.business_autonomy.provider_webhook_runtime import ProviderWebhookRuntime

    calls: list[str] = []

    class _Registry:
        def record(self, **kwargs):
            raise RuntimeError("message_store_failed")

    class _Processor:
        def process(self, *, handoff):
            calls.append("process")
            return {"accepted": True}

    monkeypatch.setattr(ProviderWebhookRuntime, "verify", lambda self, **kwargs: True)
    service = ProviderInboundWebhookService(
        webhook_runtime=ProviderWebhookRuntime(None),
        replay_guard=ProviderWebhookReplayGuard(InMemoryIdempotencyStore()),
        inbound_processor=_Processor(), message_registry=_Registry(),
    )
    body = b'{"message":{"from":{"id":42},"text":"hello","message_id":9},"update_id":123}'
    with pytest.raises(RuntimeError, match="message_store_failed"):
        service.ingest(
            provider=provider_map()["telegram_bot"], tenant_id="tenant-a", business_id="business-a",
            headers={}, body=body, event_key="evt-message-fail", topic="telegram_update",
            owner_id="provider_admin",
        )
    assert calls == []


def test_message_rejects_business_scope_mismatch() -> None:
    registry, _ = _registry()
    with pytest.raises(ValueError, match="business scope mismatch"):
        registry.record(identity=_identity(), business_id="business-other", occurred_at_ms=1)


def test_default_business_autonomy_service_wires_canonical_ontology_event_store(tmp_path, monkeypatch) -> None:
    from runtime.business_autonomy.bootstrap import build_business_autonomy_guarded_service

    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.setenv("STORAGE_BACKEND", "sqlite")
    monkeypatch.delenv("EVENTS_SQLITE_PATH", raising=False)
    service = build_business_autonomy_guarded_service(business_id="message-wiring")
    try:
        assert service._provider_admin_service.customer_registry is not None
        assert service._conversation_registry is not None
        assert service._message_registry is not None
        assert service._ontology_event_store.ping() is True
        assert service._ontology_event_store._path == str(tmp_path / "runtime" / "events.db")
        assert service._ontology_event_store_stack is not None
    finally:
        service._ontology_event_store_finalizer()


def test_registry_reference_keeps_owned_ontology_event_store_alive(tmp_path, monkeypatch) -> None:
    import gc
    import weakref

    from runtime.business_autonomy.bootstrap import build_business_autonomy_guarded_service

    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.setenv("STORAGE_BACKEND", "sqlite")
    monkeypatch.delenv("EVENTS_SQLITE_PATH", raising=False)
    service = build_business_autonomy_guarded_service(business_id="message-lifetime")
    registry = service._message_registry
    store_ref = weakref.ref(service._ontology_event_store)
    del service
    gc.collect()

    store = store_ref()
    assert registry is not None
    assert store is not None
    assert store.ping() is True


def test_business_autonomy_service_does_not_own_injected_event_store(tmp_path, monkeypatch) -> None:
    from runtime.business_autonomy.bootstrap import build_business_autonomy_guarded_service
    from runtime.platform.event_store.sqlite_event_store import SqliteEventStore

    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.setenv("STORAGE_BACKEND", "sqlite")
    path = tmp_path / "injected-events.db"
    with SqliteEventStore(str(path)) as events:
        service = build_business_autonomy_guarded_service(
            business_id="message-wiring-injected",
            customer_event_store=events,
        )
        assert service._ontology_event_store is events
        assert service._ontology_event_store_stack is None
        assert service._message_registry is not None
        assert events.ping() is True


def test_message_event_metadata_propagates_and_archive_replay_rejects_change() -> None:
    registry, events = _registry()
    record_metadata = {"actor_id": "owner-1", "decision_id": "message-record", "evidence_ids": ("e-message",)}
    recorded = registry.record( identity=_identity(message_id="provider-meta"), customer_id="customer-a", occurred_at_ms=10, event_metadata=record_metadata, )
    assert registry.record( identity=_identity(message_id="provider-meta"), customer_id="customer-a", occurred_at_ms=999, event_metadata=record_metadata, ) == recorded
    rows = list(events.iter_events(tenant_id="tenant-a", start_ms=0))
    assert canonical_business_event_contract(rows[0])["actor_id"] == "owner-1"
    with pytest.raises(ValueError, match="event metadata"):
        registry.record( identity=_identity(message_id="provider-meta"), customer_id="customer-a", occurred_at_ms=10, event_metadata={**record_metadata, "actor_id": "owner-2"}, )
    archive_metadata = {"actor_id": "owner-1", "decision_id": "message-archive"}
    archived = registry.archive( tenant_id="tenant-a", business_id="business-a", message_id=recorded.message_id, idempotency_key="archive-meta", occurred_at_ms=20, event_metadata=archive_metadata, )
    assert registry.archive( tenant_id="tenant-a", business_id="business-a", message_id=recorded.message_id, idempotency_key="archive-meta", occurred_at_ms=999, event_metadata=archive_metadata, ) == archived
    with pytest.raises(ValueError, match="event metadata"):
        registry.archive( tenant_id="tenant-a", business_id="business-a", message_id=recorded.message_id, idempotency_key="archive-meta", occurred_at_ms=20, event_metadata={**archive_metadata, "actor_id": "owner-2"}, )

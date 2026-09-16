from __future__ import annotations

from types import SimpleNamespace

import pytest

from contracts.event_store import BusinessFactV1
from reliability.idempotency_store import InMemoryIdempotencyStore
from runtime.messaging.conversation_registry import (
    CONVERSATION_ACTIVITY_OBSERVED,
    CONVERSATION_SCHEMA_VERSION,
    ConversationHistoryInvariantViolation,
    ConversationLifecycleStatus,
    ConversationProjector,
    ConversationRegistry,
    conversation_id_for,
)
from runtime.platform.event_store.memory_event_store import MemoryEventStore


class _Customers:
    def __init__(self, *, active: bool = True) -> None:
        self.active = active

    def get_customer(self, *, tenant_id: str, business_id: str, customer_id: str):
        status = SimpleNamespace(value="active" if self.active else "archived")
        return SimpleNamespace(customer=SimpleNamespace(customer_id=customer_id, status=status))


def _registry(*, events=None, active_customer: bool = True):
    store = events or MemoryEventStore()
    return (
        ConversationRegistry(
            event_store=store,
            idempotency_store=InMemoryIdempotencyStore(),
            customer_registry=_Customers(active=active_customer),
        ),
        store,
    )


def test_conversation_ingress_is_deterministic_pii_free_and_idempotent() -> None:
    registry, events = _registry()
    first = registry.ensure_ingress(
        tenant_id="tenant-a",
        business_id="business-a",
        customer_id="customer-a",
        channel="Telegram",
        route_ref="raw-chat-123",
        contact_id="raw-message-456",
        occurred_at_ms=100,
    )
    replay = registry.ensure_ingress(
        tenant_id="tenant-a",
        business_id="business-a",
        customer_id="customer-a",
        channel="telegram",
        route_ref="raw-chat-123",
        contact_id="raw-message-456",
        occurred_at_ms=200,
    )
    assert first.conversation_id == conversation_id_for(
        tenant_id="tenant-a", business_id="business-a", channel="telegram", route_ref="raw-chat-123"
    )
    assert replay.activity_count == 1
    assert replay.channel == "telegram"
    assert replay.lifecycle_status is ConversationLifecycleStatus.OPEN
    serialized = repr(list(events))
    assert "raw-chat-123" not in serialized
    assert "raw-message-456" not in serialized


def test_conversation_requires_active_canonical_customer() -> None:
    registry, _ = _registry(active_customer=False)
    with pytest.raises(ValueError, match="active customer"):
        registry.ensure_ingress(
            tenant_id="t", business_id="b", customer_id="c", channel="vk",
            route_ref="route", contact_id="message",
        )


def test_conversation_archive_is_terminal() -> None:
    registry, _ = _registry()
    current = registry.ensure_ingress(
        tenant_id="t", business_id="b", customer_id="c", channel="max",
        route_ref="route", contact_id="message", occurred_at_ms=10,
    )
    archived = registry.archive(
        tenant_id="t", business_id="b", conversation_id=current.conversation_id,
        idempotency_key="archive", occurred_at_ms=20,
    )
    assert archived.lifecycle_status is ConversationLifecycleStatus.ARCHIVED
    with pytest.raises(ValueError, match="archived conversation"):
        registry.ensure_ingress(
            tenant_id="t", business_id="b", customer_id="c", channel="max",
            route_ref="route", contact_id="message-2", occurred_at_ms=30,
        )


def test_conversation_projection_fails_closed_on_corrupted_history() -> None:
    registry, events = _registry()
    current = registry.ensure_ingress(
        tenant_id="t", business_id="b", customer_id="c", channel="telegram",
        route_ref="route", contact_id="message", occurred_at_ms=10,
    )
    registry.archive(
        tenant_id="t", business_id="b", conversation_id=current.conversation_id,
        idempotency_key="archive", occurred_at_ms=20,
    )
    events.append_event(BusinessFactV1(
        fact_id="corrupt", tenant_id="t", business_id="b",
        fact_type=CONVERSATION_ACTIVITY_OBSERVED, entity_id=current.conversation_id,
        event_time_ms=30, observed_at_ms=30, source="conversation_registry",
        payload={"schema_version": CONVERSATION_SCHEMA_VERSION, "contact_digest": "0" * 64},
    ).as_event())
    with pytest.raises(ConversationHistoryInvariantViolation, match="continues after archive"):
        ConversationProjector(events).get(
            tenant_id="t", business_id="b", conversation_id=current.conversation_id
        )


def test_conversation_projection_rejects_noncanonical_source() -> None:
    events = MemoryEventStore()
    events.append_event(BusinessFactV1(
        fact_id="bad", tenant_id="t", business_id="b", fact_type="conversation.created",
        entity_id="conversation:bad", event_time_ms=1, observed_at_ms=1, source="other",
        payload={
            "schema_version": CONVERSATION_SCHEMA_VERSION,
            "customer_id": "c", "channel": "telegram", "route_digest": "0" * 64,
        },
    ).as_event())
    with pytest.raises(ConversationHistoryInvariantViolation, match="noncanonical source"):
        ConversationProjector(events).get(
            tenant_id="t", business_id="b", conversation_id="conversation:bad"
        )


def test_conversation_projection_survives_sqlite_restart(tmp_path) -> None:
    from runtime.platform.event_store.sqlite_event_store import SqliteEventStore

    path = tmp_path / "conversation.sqlite3"
    with SqliteEventStore(str(path)) as events:
        registry = ConversationRegistry(
            event_store=events,
            idempotency_store=InMemoryIdempotencyStore(),
            customer_registry=_Customers(),
        )
        created = registry.ensure_ingress(
            tenant_id="tenant", business_id="business", customer_id="customer",
            channel="telegram", route_ref="thread", contact_id="message", occurred_at_ms=123,
        )
    with SqliteEventStore(str(path)) as events:
        restored = ConversationProjector(events).get(
            tenant_id="tenant", business_id="business", conversation_id=created.conversation_id
        )
    assert restored.customer_id == "customer"
    assert restored.activity_count == 1
    assert restored.last_activity_at_ms == 123

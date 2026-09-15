from __future__ import annotations

import pytest

from application.deal import DealHistoryInvariantViolation, DealProjector, DealRegistry
from contracts.deal import Deal, DealLifecycleStatus, DealNotFound
from contracts.event_store import BusinessFactV1
from reliability.idempotency_store import InMemoryIdempotencyStore


class MemoryEventStore:
    def __init__(self) -> None:
        self.events: list[dict] = []

    def append_event(self, event: dict) -> None:
        self.events.append(dict(event))

    def iter_events(self, *, tenant_id: str, start_ms: int, end_ms=None, user_id=None, event_type=None):
        for event in self.events:
            if str(event.get("tenant_id") or "") != str(tenant_id):
                continue
            if int(event.get("timestamp_ms") or 0) < int(start_ms):
                continue
            if end_ms is not None and int(event.get("timestamp_ms") or 0) > int(end_ms):
                continue
            if event_type is not None and str(event.get("event_type") or "") != str(event_type):
                continue
            yield dict(event)


def _registry() -> tuple[DealRegistry, MemoryEventStore]:
    events = MemoryEventStore()
    return DealRegistry(event_store=events, idempotency_store=InMemoryIdempotencyStore()), events


def test_deal_lifecycle_is_scoped_idempotent_and_money_safe() -> None:
    registry, events = _registry()
    created = registry.create(
        tenant_id="tenant-1", business_id="business-1", deal_id="deal-1",
        idempotency_key="create-1", pipeline_key="sales", stage_key="new",
        amount_minor=12500, currency="rub", occurred_at_ms=100,
    )
    assert created.pipeline_key == "sales"
    assert created.stage_key == "new"
    assert created.amount_minor == 12500
    assert created.currency == "RUB"
    assert created.lifecycle_status is DealLifecycleStatus.ACTIVE
    assert len(events.events) == 1
    replay = registry.create(
        tenant_id="tenant-1", business_id="business-1", deal_id="deal-1",
        idempotency_key="create-1", pipeline_key="sales", stage_key="new",
        amount_minor=12500, currency="RUB", occurred_at_ms=999,
    )
    assert replay == created
    assert len(events.events) == 1

    updated = registry.update(
        tenant_id="tenant-1", business_id="business-1", deal_id="deal-1",
        idempotency_key="advance-1", stage_key="qualified", amount_minor=15000,
        occurred_at_ms=200,
    )
    assert updated.stage_key == "qualified"
    assert updated.amount_minor == 15000
    assert updated.currency == "RUB"
    assert len(events.events) == 2

    archived = registry.archive(
        tenant_id="tenant-1", business_id="business-1", deal_id="deal-1",
        idempotency_key="archive-1", occurred_at_ms=300,
    )
    assert archived.lifecycle_status is DealLifecycleStatus.ARCHIVED
    assert archived.archived_at_ms == 300
    assert len(events.events) == 3


def test_deal_pipeline_currency_and_archive_are_fail_closed() -> None:
    registry, _ = _registry()
    registry.create(
        tenant_id="tenant-1", business_id="business-1", deal_id="deal-1",
        idempotency_key="create", pipeline_key="sales", stage_key="new",
        amount_minor=100, currency="USD", occurred_at_ms=100,
    )
    with pytest.raises(ValueError, match="pipeline cannot be rewritten"):
        registry.update(
            tenant_id="tenant-1", business_id="business-1", deal_id="deal-1",
            idempotency_key="pipeline", pipeline_key="renewal", occurred_at_ms=200,
        )
    with pytest.raises(ValueError, match="currency cannot be rewritten"):
        registry.update(
            tenant_id="tenant-1", business_id="business-1", deal_id="deal-1",
            idempotency_key="currency", currency="EUR", occurred_at_ms=200,
        )
    registry.archive(
        tenant_id="tenant-1", business_id="business-1", deal_id="deal-1",
        idempotency_key="archive", occurred_at_ms=300,
    )
    with pytest.raises(ValueError, match="archived deal"):
        registry.update(
            tenant_id="tenant-1", business_id="business-1", deal_id="deal-1",
            idempotency_key="after", stage_key="won", occurred_at_ms=400,
        )


def test_deal_contract_rejects_unsafe_money() -> None:
    with pytest.raises(ValueError, match="negative"):
        Deal(deal_id="d", tenant_id="t", business_id="b", amount_minor=-1, currency="RUB")
    with pytest.raises(ValueError, match="integer minor-unit"):
        Deal(deal_id="d", tenant_id="t", business_id="b", amount_minor=1.5, currency="RUB")
    with pytest.raises(ValueError, match="integer minor-unit"):
        Deal(deal_id="d", tenant_id="t", business_id="b", amount_minor=True, currency="RUB")
    with pytest.raises(ValueError, match="currency is required"):
        Deal(deal_id="d", tenant_id="t", business_id="b", amount_minor=1)
    with pytest.raises(ValueError, match="3-letter"):
        Deal(deal_id="d", tenant_id="t", business_id="b", amount_minor=1, currency="RUBLE")


def test_deal_projection_is_tenant_and_business_scoped() -> None:
    events = MemoryEventStore()
    claims = InMemoryIdempotencyStore()
    registry = DealRegistry(event_store=events, idempotency_store=claims)
    registry.create(
        tenant_id="tenant-1", business_id="business-1", deal_id="shared",
        idempotency_key="one", pipeline_key="a", occurred_at_ms=100,
    )
    registry.create(
        tenant_id="tenant-2", business_id="business-2", deal_id="shared",
        idempotency_key="two", pipeline_key="b", occurred_at_ms=100,
    )
    projector = DealProjector(events)
    assert projector.get(tenant_id="tenant-1", business_id="business-1", deal_id="shared").pipeline_key == "a"
    assert projector.get(tenant_id="tenant-2", business_id="business-2", deal_id="shared").pipeline_key == "b"
    with pytest.raises(DealNotFound):
        projector.get(tenant_id="tenant-1", business_id="business-2", deal_id="shared")


def test_deal_projector_fails_closed_on_corrupted_history() -> None:
    events = MemoryEventStore()
    events.append_event(BusinessFactV1(
        fact_id="deal-update", tenant_id="tenant-1", business_id="business-1",
        fact_type="deal.updated", entity_id="deal-1", event_time_ms=100, observed_at_ms=100,
        source="deal_registry", payload={"pipeline_key": "sales", "stage_key": "qualified", "amount_minor": None, "currency": None},
    ).as_event())
    events.append_event(BusinessFactV1(
        fact_id="deal-create", tenant_id="tenant-1", business_id="business-1",
        fact_type="deal.created", entity_id="deal-1", event_time_ms=200, observed_at_ms=200,
        source="deal_registry", payload={"pipeline_key": "sales", "stage_key": "new", "amount_minor": None, "currency": None},
    ).as_event())
    with pytest.raises(DealHistoryInvariantViolation, match="begin with exactly one create"):
        DealProjector(events).get(tenant_id="tenant-1", business_id="business-1", deal_id="deal-1")


def test_deal_projection_survives_sqlite_event_store_restart(tmp_path) -> None:
    from runtime.platform.event_store.sqlite_event_store import SqliteEventStore

    path = tmp_path / "deal-events.sqlite3"
    with SqliteEventStore(str(path)) as events:
        registry = DealRegistry(event_store=events, idempotency_store=InMemoryIdempotencyStore())
        registry.create(
            tenant_id="tenant-real", business_id="business-real", deal_id="deal-real",
            idempotency_key="create-real", pipeline_key="sales", stage_key="new",
            amount_minor=9900, currency="EUR", occurred_at_ms=123,
        )
        registry.update(
            tenant_id="tenant-real", business_id="business-real", deal_id="deal-real",
            idempotency_key="advance-real", stage_key="proposal", amount_minor=10900,
            occurred_at_ms=234,
        )
    with SqliteEventStore(str(path)) as events:
        restored = DealProjector(events).get(
            tenant_id="tenant-real", business_id="business-real", deal_id="deal-real"
        )
    assert restored.pipeline_key == "sales"
    assert restored.stage_key == "proposal"
    assert restored.amount_minor == 10900
    assert restored.currency == "EUR"
    assert restored.created_at_ms == 123
    assert restored.updated_at_ms == 234

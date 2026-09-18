from __future__ import annotations

import pytest

from application.opportunity import OpportunityHistoryInvariantViolation, OpportunityProjector, OpportunityRegistry
from contracts.event_store import BusinessFactV1, canonical_business_event_contract
from contracts.opportunity import Opportunity, OpportunityLifecycleStatus, OpportunityNotFound
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


def _registry() -> tuple[OpportunityRegistry, MemoryEventStore]:
    events = MemoryEventStore()
    return OpportunityRegistry(event_store=events, idempotency_store=InMemoryIdempotencyStore()), events


def test_opportunity_lifecycle_is_idempotent_and_money_safe() -> None:
    registry, events = _registry()
    created = registry.create(
        tenant_id="tenant-1", business_id="business-1", opportunity_id="opp-1",
        idempotency_key="create", source_kind="crm", stage_key="new",
        expected_value_minor=25000, currency="rub", occurred_at_ms=100,
    )
    assert created.currency == "RUB"
    assert len(events.events) == 1
    assert registry.create(
        tenant_id="tenant-1", business_id="business-1", opportunity_id="opp-1",
        idempotency_key="create", source_kind="crm", stage_key="new",
        expected_value_minor=25000, currency="RUB", occurred_at_ms=999,
    ) == created
    assert len(events.events) == 1
    updated = registry.update(
        tenant_id="tenant-1", business_id="business-1", opportunity_id="opp-1",
        idempotency_key="update", stage_key="qualified", expected_value_minor=30000,
        occurred_at_ms=200,
    )
    assert updated.stage_key == "qualified"
    assert updated.expected_value_minor == 30000
    archived = registry.archive(
        tenant_id="tenant-1", business_id="business-1", opportunity_id="opp-1",
        idempotency_key="archive", occurred_at_ms=300,
    )
    assert archived.lifecycle_status is OpportunityLifecycleStatus.ARCHIVED


def test_opportunity_metadata_propagates_and_replay_rejects_change() -> None:
    registry, events = _registry()
    metadata = {"actor_id": "owner-1", "decision_id": "decision-1", "evidence_ids": ("e-1",)}
    created = registry.create(
        tenant_id="t", business_id="b", opportunity_id="o", idempotency_key="create-meta",
        source_kind="crm", stage_key="new", expected_value_minor=1000, currency="USD",
        occurred_at_ms=100, event_metadata=metadata,
    )
    assert registry.create(
        tenant_id="t", business_id="b", opportunity_id="o", idempotency_key="create-meta",
        source_kind="crm", stage_key="new", expected_value_minor=1000, currency="USD",
        occurred_at_ms=999, event_metadata=metadata,
    ) == created
    assert len(events.events) == 1
    assert canonical_business_event_contract(events.events[0])["actor_id"] == "owner-1"
    assert canonical_business_event_contract(events.events[0])["evidence_ids"] == ("e-1",)
    with pytest.raises(ValueError, match="event metadata"):
        registry.create(
            tenant_id="t", business_id="b", opportunity_id="o", idempotency_key="create-meta",
            source_kind="crm", stage_key="new", expected_value_minor=1000, currency="USD",
            occurred_at_ms=100, event_metadata={**metadata, "actor_id": "owner-2"},
        )

    update_metadata = {"actor_id": "owner-1", "decision_id": "decision-2"}
    updated = registry.update(
        tenant_id="t", business_id="b", opportunity_id="o", idempotency_key="update-meta",
        stage_key="qualified", occurred_at_ms=200, event_metadata=update_metadata,
    )
    assert registry.update(
        tenant_id="t", business_id="b", opportunity_id="o", idempotency_key="update-meta",
        stage_key="qualified", occurred_at_ms=999, event_metadata=update_metadata,
    ) == updated
    with pytest.raises(ValueError, match="event metadata"):
        registry.update(
            tenant_id="t", business_id="b", opportunity_id="o", idempotency_key="update-meta",
            stage_key="qualified", occurred_at_ms=200,
            event_metadata={**update_metadata, "actor_id": "owner-2"},
        )

    archive_metadata = {"actor_id": "owner-1", "decision_id": "decision-3"}
    archived = registry.archive(
        tenant_id="t", business_id="b", opportunity_id="o", idempotency_key="archive-meta",
        occurred_at_ms=300, event_metadata=archive_metadata,
    )
    assert registry.archive(
        tenant_id="t", business_id="b", opportunity_id="o", idempotency_key="archive-meta",
        occurred_at_ms=999, event_metadata=archive_metadata,
    ) == archived
    with pytest.raises(ValueError, match="event metadata"):
        registry.archive(
            tenant_id="t", business_id="b", opportunity_id="o", idempotency_key="archive-meta",
            occurred_at_ms=300, event_metadata={**archive_metadata, "actor_id": "owner-2"},
        )


def test_opportunity_source_currency_and_archive_are_fail_closed() -> None:
    registry, _ = _registry()
    registry.create(
        tenant_id="t", business_id="b", opportunity_id="o", idempotency_key="c",
        source_kind="crm", expected_value_minor=100, currency="USD", occurred_at_ms=100,
    )
    with pytest.raises(ValueError, match="source cannot be rewritten"):
        registry.update(tenant_id="t", business_id="b", opportunity_id="o", idempotency_key="s", source_kind="ads")
    with pytest.raises(ValueError, match="currency cannot be rewritten"):
        registry.update(tenant_id="t", business_id="b", opportunity_id="o", idempotency_key="m", currency="EUR")
    registry.archive(tenant_id="t", business_id="b", opportunity_id="o", idempotency_key="a", occurred_at_ms=300)
    with pytest.raises(ValueError, match="archived opportunity"):
        registry.update(tenant_id="t", business_id="b", opportunity_id="o", idempotency_key="x", stage_key="won")


def test_opportunity_contract_rejects_unsafe_money() -> None:
    with pytest.raises(ValueError, match="negative"):
        Opportunity(opportunity_id="o", tenant_id="t", business_id="b", expected_value_minor=-1, currency="RUB")
    with pytest.raises(ValueError, match="integer minor-unit"):
        Opportunity(opportunity_id="o", tenant_id="t", business_id="b", expected_value_minor=1.5, currency="RUB")
    with pytest.raises(ValueError, match="currency is required"):
        Opportunity(opportunity_id="o", tenant_id="t", business_id="b", expected_value_minor=1)


def test_opportunity_projection_is_scoped_and_corruption_fails_closed() -> None:
    registry, events = _registry()
    registry.create(tenant_id="t1", business_id="b1", opportunity_id="shared", idempotency_key="1", source_kind="crm", occurred_at_ms=100)
    registry.create(tenant_id="t2", business_id="b2", opportunity_id="shared", idempotency_key="2", source_kind="ads", occurred_at_ms=100)
    projector = OpportunityProjector(events)
    assert projector.get(tenant_id="t1", business_id="b1", opportunity_id="shared").source_kind == "crm"
    with pytest.raises(OpportunityNotFound):
        projector.get(tenant_id="t1", business_id="b2", opportunity_id="shared")
    corrupted = MemoryEventStore()
    corrupted.append_event(BusinessFactV1(
        fact_id="update", tenant_id="t", business_id="b", fact_type="opportunity.updated",
        entity_id="o", event_time_ms=100, observed_at_ms=100, source="opportunity_registry",
        payload={"source_kind": "crm", "stage_key": "new", "expected_value_minor": None, "currency": None},
    ).as_event())
    with pytest.raises(OpportunityHistoryInvariantViolation, match="begin with exactly one create"):
        OpportunityProjector(corrupted).get(tenant_id="t", business_id="b", opportunity_id="o")


def test_opportunity_projection_survives_sqlite_restart(tmp_path) -> None:
    from runtime.platform.event_store.sqlite_event_store import SqliteEventStore

    path = tmp_path / "opportunity.sqlite3"
    with SqliteEventStore(str(path)) as events:
        registry = OpportunityRegistry(event_store=events, idempotency_store=InMemoryIdempotencyStore())
        registry.create(
            tenant_id="tenant", business_id="business", opportunity_id="opp", idempotency_key="create",
            source_kind="process_discovery", stage_key="identified", expected_value_minor=9000,
            currency="EUR", occurred_at_ms=123,
        )
        registry.update(
            tenant_id="tenant", business_id="business", opportunity_id="opp", idempotency_key="update",
            stage_key="validated", expected_value_minor=11000, occurred_at_ms=234,
        )
    with SqliteEventStore(str(path)) as events:
        restored = OpportunityProjector(events).get(tenant_id="tenant", business_id="business", opportunity_id="opp")
    assert restored.source_kind == "process_discovery"
    assert restored.stage_key == "validated"
    assert restored.expected_value_minor == 11000
    assert restored.currency == "EUR"

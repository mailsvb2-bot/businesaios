from __future__ import annotations

import pytest

from application.campaign.projector import CampaignHistoryInvariantViolation, CampaignProjector
from application.campaign.registry import CampaignRegistry
from contracts.campaign import Campaign, CampaignLifecycleStatus, CampaignNotFound
from contracts.event_store import BusinessFactV1, canonical_business_event_contract
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


def _registry() -> tuple[CampaignRegistry, MemoryEventStore]:
    events = MemoryEventStore()
    return CampaignRegistry(event_store=events, idempotency_store=InMemoryIdempotencyStore()), events


def test_campaign_lifecycle_is_scoped_idempotent_and_money_safe() -> None:
    registry, events = _registry()
    created = registry.create(
        tenant_id="tenant-1", business_id="business-1", campaign_id="campaign-1",
        idempotency_key="create-1", channel_key="meta_ads", objective_key="leads",
        budget_minor=12500, currency="rub", occurred_at_ms=100,
    )
    assert created.channel_key == "meta_ads"
    assert created.budget_minor == 12500
    assert created.currency == "RUB"
    assert len(events.events) == 1
    replay = registry.create(
        tenant_id="tenant-1", business_id="business-1", campaign_id="campaign-1",
        idempotency_key="create-1", channel_key="meta_ads", objective_key="leads",
        budget_minor=12500, currency="RUB", occurred_at_ms=999,
    )
    assert replay == created
    assert len(events.events) == 1
    updated = registry.update(
        tenant_id="tenant-1", business_id="business-1", campaign_id="campaign-1",
        idempotency_key="update-1", objective_key="purchases", budget_minor=15000,
        occurred_at_ms=200,
    )
    assert updated.objective_key == "purchases"
    assert updated.budget_minor == 15000
    archived = registry.archive(
        tenant_id="tenant-1", business_id="business-1", campaign_id="campaign-1",
        idempotency_key="archive-1", occurred_at_ms=300,
    )
    assert archived.lifecycle_status is CampaignLifecycleStatus.ARCHIVED
    assert archived.archived_at_ms == 300


def test_campaign_metadata_propagates_and_replay_rejects_change() -> None:
    registry, events = _registry()
    create_metadata = {
        "actor_id": "owner-1",
        "decision_id": "decision-create",
        "correlation_id": "campaign-flow-1",
        "evidence_ids": ("evidence-create",),
    }
    created = registry.create(
        tenant_id="tenant-1", business_id="business-1", campaign_id="campaign-1",
        idempotency_key="create-meta", channel_key="meta_ads", objective_key="leads",
        budget_minor=12500, currency="RUB", occurred_at_ms=100,
        event_metadata=create_metadata,
    )
    assert registry.create(
        tenant_id="tenant-1", business_id="business-1", campaign_id="campaign-1",
        idempotency_key="create-meta", channel_key="meta_ads", objective_key="leads",
        budget_minor=12500, currency="RUB", occurred_at_ms=999,
        event_metadata=create_metadata,
    ) == created
    assert len(events.events) == 1
    contract = canonical_business_event_contract(events.events[0])
    assert contract["actor_id"] == "owner-1"
    assert contract["evidence_ids"] == ("evidence-create",)
    with pytest.raises(ValueError, match="event metadata"):
        registry.create(
            tenant_id="tenant-1", business_id="business-1", campaign_id="campaign-1",
            idempotency_key="create-meta", channel_key="meta_ads", objective_key="leads",
            budget_minor=12500, currency="RUB", occurred_at_ms=100,
            event_metadata={**create_metadata, "actor_id": "owner-2"},
        )

    update_metadata = {"actor_id": "owner-1", "decision_id": "decision-update"}
    updated = registry.update(
        tenant_id="tenant-1", business_id="business-1", campaign_id="campaign-1",
        idempotency_key="update-meta", objective_key="purchases", budget_minor=15000,
        occurred_at_ms=200, event_metadata=update_metadata,
    )
    assert registry.update(
        tenant_id="tenant-1", business_id="business-1", campaign_id="campaign-1",
        idempotency_key="update-meta", objective_key="purchases", budget_minor=15000,
        occurred_at_ms=999, event_metadata=update_metadata,
    ) == updated
    with pytest.raises(ValueError, match="event metadata"):
        registry.update(
            tenant_id="tenant-1", business_id="business-1", campaign_id="campaign-1",
            idempotency_key="update-meta", objective_key="purchases", budget_minor=15000,
            occurred_at_ms=200, event_metadata={**update_metadata, "actor_id": "owner-2"},
        )

    archive_metadata = {"actor_id": "owner-1", "decision_id": "decision-archive"}
    archived = registry.archive(
        tenant_id="tenant-1", business_id="business-1", campaign_id="campaign-1",
        idempotency_key="archive-meta", occurred_at_ms=300, event_metadata=archive_metadata,
    )
    assert registry.archive(
        tenant_id="tenant-1", business_id="business-1", campaign_id="campaign-1",
        idempotency_key="archive-meta", occurred_at_ms=999, event_metadata=archive_metadata,
    ) == archived
    with pytest.raises(ValueError, match="event metadata"):
        registry.archive(
            tenant_id="tenant-1", business_id="business-1", campaign_id="campaign-1",
            idempotency_key="archive-meta", occurred_at_ms=300,
            event_metadata={**archive_metadata, "actor_id": "owner-2"},
        )


def test_campaign_channel_currency_and_archive_are_fail_closed() -> None:
    registry, _ = _registry()
    registry.create(
        tenant_id="tenant-1", business_id="business-1", campaign_id="campaign-1",
        idempotency_key="create", channel_key="meta_ads", budget_minor=100,
        currency="USD", occurred_at_ms=100,
    )
    with pytest.raises(ValueError, match="channel cannot be rewritten"):
        registry.update(
            tenant_id="tenant-1", business_id="business-1", campaign_id="campaign-1",
            idempotency_key="channel", channel_key="google_ads", occurred_at_ms=200,
        )
    with pytest.raises(ValueError, match="currency cannot be rewritten"):
        registry.update(
            tenant_id="tenant-1", business_id="business-1", campaign_id="campaign-1",
            idempotency_key="currency", currency="EUR", occurred_at_ms=200,
        )
    registry.archive(
        tenant_id="tenant-1", business_id="business-1", campaign_id="campaign-1",
        idempotency_key="archive", occurred_at_ms=300,
    )
    with pytest.raises(ValueError, match="archived campaign"):
        registry.update(
            tenant_id="tenant-1", business_id="business-1", campaign_id="campaign-1",
            idempotency_key="after", objective_key="sales", occurred_at_ms=400,
        )


def test_campaign_contract_rejects_unsafe_money() -> None:
    with pytest.raises(ValueError, match="negative"):
        Campaign(campaign_id="c", tenant_id="t", business_id="b", budget_minor=-1, currency="RUB")
    with pytest.raises(ValueError, match="integer minor-unit"):
        Campaign(campaign_id="c", tenant_id="t", business_id="b", budget_minor=1.5, currency="RUB")
    with pytest.raises(ValueError, match="integer minor-unit"):
        Campaign(campaign_id="c", tenant_id="t", business_id="b", budget_minor=True, currency="RUB")
    with pytest.raises(ValueError, match="currency is required"):
        Campaign(campaign_id="c", tenant_id="t", business_id="b", budget_minor=1)


def test_campaign_projection_is_tenant_and_business_scoped() -> None:
    events = MemoryEventStore()
    claims = InMemoryIdempotencyStore()
    registry = CampaignRegistry(event_store=events, idempotency_store=claims)
    registry.create(
        tenant_id="tenant-1", business_id="business-1", campaign_id="shared",
        idempotency_key="one", channel_key="meta_ads", occurred_at_ms=100,
    )
    registry.create(
        tenant_id="tenant-2", business_id="business-2", campaign_id="shared",
        idempotency_key="two", channel_key="google_ads", occurred_at_ms=100,
    )
    projector = CampaignProjector(events)
    assert projector.get(tenant_id="tenant-1", business_id="business-1", campaign_id="shared").channel_key == "meta_ads"
    assert projector.get(tenant_id="tenant-2", business_id="business-2", campaign_id="shared").channel_key == "google_ads"
    with pytest.raises(CampaignNotFound):
        projector.get(tenant_id="tenant-1", business_id="business-2", campaign_id="shared")


def test_campaign_projector_fails_closed_on_corrupted_history() -> None:
    events = MemoryEventStore()
    events.append_event(BusinessFactV1(
        fact_id="campaign-update", tenant_id="tenant-1", business_id="business-1",
        fact_type="campaign.updated", entity_id="campaign-1", event_time_ms=100, observed_at_ms=100,
        source="campaign_registry", payload={"channel_key": "meta_ads", "objective_key": "sales", "budget_minor": None, "currency": None},
    ).as_event())
    events.append_event(BusinessFactV1(
        fact_id="campaign-create", tenant_id="tenant-1", business_id="business-1",
        fact_type="campaign.created", entity_id="campaign-1", event_time_ms=200, observed_at_ms=200,
        source="campaign_registry", payload={"channel_key": "meta_ads", "objective_key": "leads", "budget_minor": None, "currency": None},
    ).as_event())
    with pytest.raises(CampaignHistoryInvariantViolation, match="begin with exactly one create"):
        CampaignProjector(events).get(tenant_id="tenant-1", business_id="business-1", campaign_id="campaign-1")


def test_campaign_projection_survives_sqlite_event_store_restart(tmp_path) -> None:
    from runtime.platform.event_store.sqlite_event_store import SqliteEventStore

    path = tmp_path / "campaign-events.sqlite3"
    with SqliteEventStore(str(path)) as events:
        registry = CampaignRegistry(event_store=events, idempotency_store=InMemoryIdempotencyStore())
        registry.create(
            tenant_id="tenant-real", business_id="business-real", campaign_id="campaign-real",
            idempotency_key="create-real", channel_key="meta_ads", objective_key="leads",
            budget_minor=9900, currency="EUR", occurred_at_ms=123,
        )
        registry.update(
            tenant_id="tenant-real", business_id="business-real", campaign_id="campaign-real",
            idempotency_key="update-real", objective_key="purchases", budget_minor=10900,
            occurred_at_ms=234,
        )
    with SqliteEventStore(str(path)) as events:
        restored = CampaignProjector(events).get(
            tenant_id="tenant-real", business_id="business-real", campaign_id="campaign-real"
        )
    assert restored.channel_key == "meta_ads"
    assert restored.objective_key == "purchases"
    assert restored.budget_minor == 10900
    assert restored.currency == "EUR"

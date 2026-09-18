from __future__ import annotations

from dataclasses import fields

import pytest

from application.organization import OrganizationRegistry
from contracts.event_store import canonical_business_event_contract
from application.partner import PartnerProjector, PartnerRegistry
from application.person import PersonRegistry
from contracts.organization import OrganizationNotFound
from contracts.partner import Partner, PartnerNotFound, PartnerPartyKind, PartnerStatus
from contracts.person import PersonNotFound
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

    def count_events(self, *, tenant_id: str, start_ms: int, end_ms: int, user_id=None, event_type=None) -> int:
        return sum(1 for _ in self.iter_events(tenant_id=tenant_id, start_ms=start_ms, end_ms=end_ms, user_id=user_id, event_type=event_type))


def _stack():
    events = MemoryEventStore()
    claims = InMemoryIdempotencyStore()
    organizations = OrganizationRegistry(event_store=events, idempotency_store=claims)
    people = PersonRegistry(event_store=events, idempotency_store=claims)
    partners = PartnerRegistry(event_store=events, idempotency_store=claims)
    return events, organizations, people, partners


def _seed(organizations, people):
    organizations.create(
        tenant_id="tenant-1", business_id="business-1", organization_id="org-1",
        idempotency_key="org", occurred_at_ms=1,
    )
    people.create(
        tenant_id="tenant-1", business_id="business-1", person_id="person-1",
        idempotency_key="person", occurred_at_ms=1,
    )


def test_partner_contract_is_pii_minimal_party_relationship() -> None:
    assert tuple(field.name for field in fields(Partner)) == (
        "partner_id", "tenant_id", "business_id", "party_kind", "party_id",
        "status", "created_at_ms", "updated_at_ms", "archived_at_ms",
    )


def test_partner_supports_person_and_organization_parties() -> None:
    _, organizations, people, partners = _stack()
    _seed(organizations, people)
    person_partner = partners.create(
        tenant_id="tenant-1", business_id="business-1", partner_id="partner-person",
        party_kind=PartnerPartyKind.PERSON, party_id="person-1", idempotency_key="partner-person", occurred_at_ms=2,
    )
    org_partner = partners.create(
        tenant_id="tenant-1", business_id="business-1", partner_id="partner-org",
        party_kind=PartnerPartyKind.ORGANIZATION, party_id="org-1", idempotency_key="partner-org", occurred_at_ms=2,
    )
    assert person_partner.party_kind is PartnerPartyKind.PERSON
    assert person_partner.party_id == "person-1"
    assert org_partner.party_kind is PartnerPartyKind.ORGANIZATION
    assert org_partner.party_id == "org-1"


def test_partner_requires_existing_party() -> None:
    _, organizations, people, partners = _stack()
    with pytest.raises(PersonNotFound):
        partners.create(
            tenant_id="tenant-1", business_id="business-1", partner_id="p1",
            party_kind="person", party_id="missing", idempotency_key="p1", occurred_at_ms=1,
        )
    with pytest.raises(OrganizationNotFound):
        partners.create(
            tenant_id="tenant-1", business_id="business-1", partner_id="p2",
            party_kind="organization", party_id="missing", idempotency_key="p2", occurred_at_ms=1,
        )
    del organizations, people


def test_partner_relationship_identity_cannot_be_rebound() -> None:
    _, organizations, people, partners = _stack()
    _seed(organizations, people)
    partners.create(
        tenant_id="tenant-1", business_id="business-1", partner_id="partner-1",
        party_kind="person", party_id="person-1", idempotency_key="create-1", occurred_at_ms=2,
    )
    with pytest.raises(ValueError, match="different party identity"):
        partners.create(
            tenant_id="tenant-1", business_id="business-1", partner_id="partner-1",
            party_kind="organization", party_id="org-1", idempotency_key="create-2", occurred_at_ms=3,
        )


def test_partner_rejects_archived_party() -> None:
    _, organizations, people, partners = _stack()
    _seed(organizations, people)
    people.archive(
        tenant_id="tenant-1", business_id="business-1", person_id="person-1",
        idempotency_key="person-archive", occurred_at_ms=2,
    )
    with pytest.raises(ValueError, match="active person"):
        partners.create(
            tenant_id="tenant-1", business_id="business-1", partner_id="partner-1",
            party_kind="person", party_id="person-1", idempotency_key="p", occurred_at_ms=3,
        )
    organizations.archive(
        tenant_id="tenant-1", business_id="business-1", organization_id="org-1",
        idempotency_key="org-archive", occurred_at_ms=2,
    )
    with pytest.raises(ValueError, match="active organization"):
        partners.create(
            tenant_id="tenant-1", business_id="business-1", partner_id="partner-2",
            party_kind="organization", party_id="org-1", idempotency_key="o", occurred_at_ms=3,
        )


def test_partner_lifecycle_is_idempotent_and_scoped() -> None:
    events, organizations, people, partners = _stack()
    _seed(organizations, people)
    created = partners.create(
        tenant_id="tenant-1", business_id="business-1", partner_id="partner-1",
        party_kind="person", party_id="person-1", idempotency_key="create", occurred_at_ms=2,
    )
    replay = partners.create(
        tenant_id="tenant-1", business_id="business-1", partner_id="partner-1",
        party_kind="person", party_id="person-1", idempotency_key="create", occurred_at_ms=999,
    )
    assert replay == created
    archived = partners.archive(
        tenant_id="tenant-1", business_id="business-1", partner_id="partner-1",
        idempotency_key="archive", occurred_at_ms=3,
    )
    assert archived.status is PartnerStatus.ARCHIVED
    assert len([e for e in events.events if dict(e.get("payload") or {}).get("fact_type", "").startswith("partner.")]) == 2
    projector = PartnerProjector(events)
    with pytest.raises(PartnerNotFound):
        projector.get(tenant_id="tenant-1", business_id="other", partner_id="partner-1")


def test_partner_event_metadata_propagates_and_replay_rejects_change() -> None:
    events, organizations, people, partners = _stack()
    _seed(organizations, people)
    create_metadata = {"actor_id": "owner-1", "decision_id": "partner-create", "evidence_ids": ("e-partner",)}
    created = partners.create(
        tenant_id="tenant-1", business_id="business-1", partner_id="partner-meta",
        party_kind="person", party_id="person-1", idempotency_key="create-meta",
        occurred_at_ms=10, event_metadata=create_metadata,
    )
    assert partners.create(
        tenant_id="tenant-1", business_id="business-1", partner_id="partner-meta",
        party_kind="person", party_id="person-1", idempotency_key="create-meta",
        occurred_at_ms=999, event_metadata=create_metadata,
    ) == created
    partner_events = [e for e in events.events if str(dict(e.get("payload") or {}).get("fact_type") or "").startswith("partner.")]
    assert canonical_business_event_contract(partner_events[0])["actor_id"] == "owner-1"
    with pytest.raises(ValueError, match="event metadata"):
        partners.create(
            tenant_id="tenant-1", business_id="business-1", partner_id="partner-meta",
            party_kind="person", party_id="person-1", idempotency_key="create-meta",
            occurred_at_ms=10, event_metadata={**create_metadata, "actor_id": "owner-2"},
        )

    archive_metadata = {"actor_id": "owner-1", "decision_id": "partner-archive"}
    archived = partners.archive(
        tenant_id="tenant-1", business_id="business-1", partner_id="partner-meta",
        idempotency_key="archive-meta", occurred_at_ms=20, event_metadata=archive_metadata,
    )
    assert partners.archive(
        tenant_id="tenant-1", business_id="business-1", partner_id="partner-meta",
        idempotency_key="archive-meta", occurred_at_ms=999, event_metadata=archive_metadata,
    ) == archived
    with pytest.raises(ValueError, match="event metadata"):
        partners.archive(
            tenant_id="tenant-1", business_id="business-1", partner_id="partner-meta",
            idempotency_key="archive-meta", occurred_at_ms=20,
            event_metadata={**archive_metadata, "actor_id": "owner-2"},
        )

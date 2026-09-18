from __future__ import annotations

import time
from typing import Any

from application.ontology import EventFactLifecycleWriter
from application.organization.projector import OrganizationProjector
from application.partner.projector import PARTNER_ARCHIVED, PARTNER_CREATED, PartnerProjector
from application.person.projector import PersonProjector
from contracts.organization import OrganizationStatus
from contracts.partner import Partner, PartnerPartyKind, PartnerStatus
from contracts.person import PersonStatus
from reliability.idempotency_contract import IdempotencyStore

CANON_PARTNER_LIFECYCLE_OWNER = True


class PartnerRegistry:
    def __init__(self, *, event_store: Any, idempotency_store: IdempotencyStore) -> None:
        self._projector = PartnerProjector(event_store)
        self._people = PersonProjector(event_store)
        self._organizations = OrganizationProjector(event_store)
        self._writer = EventFactLifecycleWriter(
            event_store=event_store, idempotency_store=idempotency_store,
            namespace="partner_fact", source="partner_registry", id_prefix="partner",
        )

    @staticmethod
    def _time(value: int | None) -> int:
        return int(time.time() * 1000) if value is None else max(0, int(value))

    def _validate_party(self, *, tenant_id: str, business_id: str, party_kind: PartnerPartyKind, party_id: str) -> str:
        if party_kind is PartnerPartyKind.PERSON:
            person = self._people.get(tenant_id=tenant_id, business_id=business_id, person_id=party_id)
            if person.status is not PersonStatus.ACTIVE:
                raise ValueError("partner requires active person")
            return person.person_id
        organization = self._organizations.get(tenant_id=tenant_id, business_id=business_id, organization_id=party_id)
        if organization.status is not OrganizationStatus.ACTIVE:
            raise ValueError("partner requires active organization")
        return organization.organization_id

    def create(
        self, *, tenant_id: str, business_id: str, partner_id: str, party_kind: PartnerPartyKind | str,
        party_id: str, idempotency_key: str, occurred_at_ms: int | None = None,
        event_metadata: dict[str, object] | None = None,
    ) -> Partner:
        kind = PartnerPartyKind(party_kind)
        bound_party_id = self._validate_party(
            tenant_id=tenant_id, business_id=business_id, party_kind=kind, party_id=party_id,
        )
        when = self._time(occurred_at_ms)
        candidate = Partner(
            partner_id=partner_id, tenant_id=tenant_id, business_id=business_id,
            party_kind=kind, party_id=bound_party_id, created_at_ms=when, updated_at_ms=when,
        )
        payload = {"party_kind": candidate.party_kind.value, "party_id": candidate.party_id}
        try:
            current = self._projector.get(tenant_id=tenant_id, business_id=business_id, partner_id=partner_id)
        except LookupError:
            current = None
        if current is not None:
            if current.party_kind is not candidate.party_kind or current.party_id != candidate.party_id:
                raise ValueError("partner already exists with different party identity")
            self._writer.repair_existing(
                tenant_id=tenant_id, business_id=business_id, entity_id=partner_id,
                operation="create", idempotency_key=idempotency_key, fact_type=PARTNER_CREATED, payload=payload,
                event_metadata=event_metadata,
            )
            return current
        self._writer.append_once(
            tenant_id=tenant_id, business_id=business_id, entity_id=partner_id,
            operation="create", idempotency_key=idempotency_key, fact_type=PARTNER_CREATED,
            payload=payload, occurred_at_ms=when, event_metadata=event_metadata,
        )
        return self._projector.get(tenant_id=tenant_id, business_id=business_id, partner_id=partner_id)

    def archive(self, *, tenant_id: str, business_id: str, partner_id: str, idempotency_key: str, occurred_at_ms: int | None = None, event_metadata: dict[str, object] | None = None) -> Partner:
        current = self._projector.get(tenant_id=tenant_id, business_id=business_id, partner_id=partner_id)
        if current.status is PartnerStatus.ARCHIVED:
            self._writer.repair_existing(
                tenant_id=tenant_id, business_id=business_id, entity_id=partner_id,
                operation="archive", idempotency_key=idempotency_key, fact_type=PARTNER_ARCHIVED, payload={},
                event_metadata=event_metadata,
            )
            return current
        when = max(current.updated_at_ms, self._time(occurred_at_ms))
        self._writer.append_once(
            tenant_id=tenant_id, business_id=business_id, entity_id=partner_id,
            operation="archive", idempotency_key=idempotency_key, fact_type=PARTNER_ARCHIVED,
            payload={}, occurred_at_ms=when, event_metadata=event_metadata,
        )
        return self._projector.get(tenant_id=tenant_id, business_id=business_id, partner_id=partner_id)

    def get(self, *, tenant_id: str, business_id: str, partner_id: str) -> Partner:
        return self._projector.get(tenant_id=tenant_id, business_id=business_id, partner_id=partner_id)

    def list_for_business(self, *, tenant_id: str, business_id: str) -> tuple[Partner, ...]:
        return self._projector.list_for_business(tenant_id=tenant_id, business_id=business_id)


__all__ = ["CANON_PARTNER_LIFECYCLE_OWNER", "PartnerRegistry"]

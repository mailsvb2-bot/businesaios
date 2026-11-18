from __future__ import annotations

import time
from dataclasses import replace
from typing import Any

from application.ontology import EventFactLifecycleWriter
from application.organization.facts import ORGANIZATION_ARCHIVED, ORGANIZATION_CREATED, ORGANIZATION_UPDATED
from application.organization.projector import OrganizationProjector
from contracts.organization import Organization, OrganizationStatus
from reliability.idempotency_contract import IdempotencyStore

CANON_ORGANIZATION_LIFECYCLE_OWNER = True


class OrganizationRegistry:
    """Single Organization lifecycle writer backed by the canonical EventStore."""

    def __init__(self, *, event_store: Any, idempotency_store: IdempotencyStore) -> None:
        self._projector = OrganizationProjector(event_store)
        self._writer = EventFactLifecycleWriter(
            event_store=event_store,
            idempotency_store=idempotency_store,
            namespace="organization_fact",
            source="organization_registry",
            id_prefix="organization",
        )

    @staticmethod
    def _time(value: int | None) -> int:
        return int(time.time() * 1000) if value is None else max(0, int(value))

    def _persist(
        self, *, tenant_id: str, business_id: str, organization_id: str,
        idempotency_key: str, operation: str, fact_type: str,
        payload: dict[str, object], event_metadata: dict[str, object] | None,
        when: int, unchanged: bool = False,
    ) -> Organization:
        """One canonical lifecycle write/repair contract for all mutations."""
        scope = dict(
            tenant_id=tenant_id, business_id=business_id,
            entity_id=organization_id, operation=operation,
            idempotency_key=idempotency_key, fact_type=fact_type,
            payload=payload, event_metadata=event_metadata,
        )
        if unchanged:
            self._writer.repair_existing(**scope)
        else:
            self._writer.append_once(**scope, occurred_at_ms=when)
        return self._projector.get(
            tenant_id=tenant_id, business_id=business_id, organization_id=organization_id,
        )

    def create(
        self, *, tenant_id: str, business_id: str, organization_id: str,
        idempotency_key: str, name: str | None = None,
        organization_type: str | None = None, occurred_at_ms: int | None = None,
        event_metadata: dict[str, object] | None = None,
    ) -> Organization:
        when = self._time(occurred_at_ms)
        candidate = Organization(
            organization_id=organization_id, tenant_id=tenant_id, business_id=business_id,
            name=name, organization_type=organization_type,
            created_at_ms=when, updated_at_ms=when,
        )
        try:
            current = self._projector.get(
                tenant_id=tenant_id, business_id=business_id, organization_id=organization_id,
            )
        except LookupError:
            current = None
        payload = {"name": candidate.name, "organization_type": candidate.organization_type}
        if current is not None and (
            current.name != candidate.name or current.organization_type != candidate.organization_type
        ):
            raise ValueError("organization already exists with different identity metadata")
        return self._persist(
            tenant_id=tenant_id, business_id=business_id, organization_id=organization_id,
            idempotency_key=idempotency_key, operation="create", fact_type=ORGANIZATION_CREATED,
            payload=payload, event_metadata=event_metadata, when=when, unchanged=current is not None,
        )

    def update(
        self, *, tenant_id: str, business_id: str, organization_id: str,
        idempotency_key: str, name: str | None = None,
        organization_type: str | None = None, occurred_at_ms: int | None = None,
        event_metadata: dict[str, object] | None = None,
    ) -> Organization:
        current = self._projector.get(
            tenant_id=tenant_id, business_id=business_id, organization_id=organization_id,
        )
        if current.status is OrganizationStatus.ARCHIVED:
            raise ValueError("archived organization cannot be updated")
        candidate = replace(
            current, name=current.name if name is None else name,
            organization_type=current.organization_type if organization_type is None else organization_type,
            updated_at_ms=max(current.updated_at_ms, self._time(occurred_at_ms)),
        )
        return self._persist(
            tenant_id=tenant_id, business_id=business_id, organization_id=organization_id,
            idempotency_key=idempotency_key, operation="update", fact_type=ORGANIZATION_UPDATED,
            payload={"name": candidate.name, "organization_type": candidate.organization_type},
            event_metadata=event_metadata, when=candidate.updated_at_ms,
            unchanged=candidate.name == current.name and candidate.organization_type == current.organization_type,
        )

    def archive(
        self, *, tenant_id: str, business_id: str, organization_id: str,
        idempotency_key: str, occurred_at_ms: int | None = None,
        event_metadata: dict[str, object] | None = None,
    ) -> Organization:
        current = self._projector.get(
            tenant_id=tenant_id, business_id=business_id, organization_id=organization_id,
        )
        return self._persist(
            tenant_id=tenant_id, business_id=business_id, organization_id=organization_id,
            idempotency_key=idempotency_key, operation="archive", fact_type=ORGANIZATION_ARCHIVED,
            payload={}, event_metadata=event_metadata,
            when=max(current.updated_at_ms, self._time(occurred_at_ms)),
            unchanged=current.status is OrganizationStatus.ARCHIVED,
        )

    def get(self, *, tenant_id: str, business_id: str, organization_id: str) -> Organization:
        return self._projector.get(tenant_id=tenant_id, business_id=business_id, organization_id=organization_id)

    def get_business_organization(self, *, tenant_id: str, business_id: str) -> Organization:\n        """Resolve the business organization via the canonical registry owner."""\n        return self.get(tenant_id=tenant_id, business_id=business_id, organization_id=business_id)\n\n    def list_for_business(self, *, tenant_id: str, business_id: str) -> tuple[Organization, ...]:
        return self._projector.list_for_business(tenant_id=tenant_id, business_id=business_id)


def business_organization(registry: OrganizationRegistry, *, tenant_id: str, business_id: str) -> Organization | None:
    """Read canonical business organization (business ID is its stable identity)."""
    try:
        return registry.get_business_organization(tenant_id=tenant_id, business_id=business_id)
    except LookupError:
        return None


def active_businesses(event_store: Any, *, tenant_id: str) -> dict[str, str]:
    """Canonical active Organizations provide the allowed business-picker options."""
    projector = OrganizationProjector(event_store)
    found: dict[str, str] = {}
    for business_id in projector.business_ids(tenant_id=tenant_id):
        active = [item for item in projector.list_for_business(tenant_id=tenant_id, business_id=business_id)
                  if item.status is OrganizationStatus.ACTIVE]
        if active:
            own = next((item for item in active if item.organization_id == business_id), active[0])
            found[business_id] = str(own.name or business_id)
    return found


__all__ = ["CANON_ORGANIZATION_LIFECYCLE_OWNER", "OrganizationRegistry", "active_businesses", "business_organization"]

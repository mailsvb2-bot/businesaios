from __future__ import annotations

import time
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

    def create(
        self,
        *,
        tenant_id: str,
        business_id: str,
        organization_id: str,
        idempotency_key: str,
        name: str | None = None,
        organization_type: str | None = None,
        occurred_at_ms: int | None = None,
    ) -> Organization:
        when = self._time(occurred_at_ms)
        candidate = Organization(
            organization_id=organization_id,
            tenant_id=tenant_id,
            business_id=business_id,
            name=name,
            organization_type=organization_type,
            created_at_ms=when,
            updated_at_ms=when,
        )
        try:
            current = self._projector.get(
                tenant_id=candidate.tenant_id,
                business_id=candidate.business_id,
                organization_id=candidate.organization_id,
            )
        except LookupError:
            current = None
        payload = {"name": candidate.name, "organization_type": candidate.organization_type}
        if current is not None:
            if current.name != candidate.name or current.organization_type != candidate.organization_type:
                raise ValueError("organization already exists with different identity metadata")
            self._writer.repair_existing(
                tenant_id=tenant_id,
                business_id=business_id,
                entity_id=organization_id,
                operation="create",
                idempotency_key=idempotency_key,
                fact_type=ORGANIZATION_CREATED,
                payload=payload,
            )
            return current
        self._writer.append_once(
            tenant_id=tenant_id,
            business_id=business_id,
            entity_id=organization_id,
            operation="create",
            idempotency_key=idempotency_key,
            fact_type=ORGANIZATION_CREATED,
            payload=payload,
            occurred_at_ms=when,
        )
        return self._projector.get(tenant_id=tenant_id, business_id=business_id, organization_id=organization_id)

    def update(
        self,
        *,
        tenant_id: str,
        business_id: str,
        organization_id: str,
        idempotency_key: str,
        name: str | None = None,
        organization_type: str | None = None,
        occurred_at_ms: int | None = None,
    ) -> Organization:
        current = self._projector.get(tenant_id=tenant_id, business_id=business_id, organization_id=organization_id)
        if current.status is OrganizationStatus.ARCHIVED:
            raise ValueError("archived organization cannot be updated")
        when = max(current.updated_at_ms, self._time(occurred_at_ms))
        candidate = Organization(
            organization_id=current.organization_id,
            tenant_id=current.tenant_id,
            business_id=current.business_id,
            name=current.name if name is None else name,
            organization_type=current.organization_type if organization_type is None else organization_type,
            created_at_ms=current.created_at_ms,
            updated_at_ms=when,
        )
        payload = {"name": candidate.name, "organization_type": candidate.organization_type}
        if candidate.name == current.name and candidate.organization_type == current.organization_type:
            self._writer.repair_existing(
                tenant_id=tenant_id,
                business_id=business_id,
                entity_id=organization_id,
                operation="update",
                idempotency_key=idempotency_key,
                fact_type=ORGANIZATION_UPDATED,
                payload=payload,
            )
            return current
        self._writer.append_once(
            tenant_id=tenant_id,
            business_id=business_id,
            entity_id=organization_id,
            operation="update",
            idempotency_key=idempotency_key,
            fact_type=ORGANIZATION_UPDATED,
            payload=payload,
            occurred_at_ms=when,
        )
        return self._projector.get(tenant_id=tenant_id, business_id=business_id, organization_id=organization_id)

    def archive(
        self,
        *,
        tenant_id: str,
        business_id: str,
        organization_id: str,
        idempotency_key: str,
        occurred_at_ms: int | None = None,
    ) -> Organization:
        current = self._projector.get(tenant_id=tenant_id, business_id=business_id, organization_id=organization_id)
        if current.status is OrganizationStatus.ARCHIVED:
            self._writer.repair_existing(
                tenant_id=tenant_id,
                business_id=business_id,
                entity_id=organization_id,
                operation="archive",
                idempotency_key=idempotency_key,
                fact_type=ORGANIZATION_ARCHIVED,
                payload={},
            )
            return current
        when = max(current.updated_at_ms, self._time(occurred_at_ms))
        self._writer.append_once(
            tenant_id=tenant_id,
            business_id=business_id,
            entity_id=organization_id,
            operation="archive",
            idempotency_key=idempotency_key,
            fact_type=ORGANIZATION_ARCHIVED,
            payload={},
            occurred_at_ms=when,
        )
        return self._projector.get(tenant_id=tenant_id, business_id=business_id, organization_id=organization_id)

    def get(self, *, tenant_id: str, business_id: str, organization_id: str) -> Organization:
        return self._projector.get(tenant_id=tenant_id, business_id=business_id, organization_id=organization_id)

    def list_for_business(self, *, tenant_id: str, business_id: str) -> tuple[Organization, ...]:
        return self._projector.list_for_business(tenant_id=tenant_id, business_id=business_id)


__all__ = ["CANON_ORGANIZATION_LIFECYCLE_OWNER", "OrganizationRegistry"]

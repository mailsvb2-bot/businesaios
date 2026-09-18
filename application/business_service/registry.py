from __future__ import annotations

import time
from typing import Any

from application.business_service.facts import (
    BUSINESS_SERVICE_ARCHIVED,
    BUSINESS_SERVICE_CREATED,
    BUSINESS_SERVICE_UPDATED,
)
from application.business_service.projector import BusinessServiceProjector
from application.ontology import EventFactLifecycleWriter
from contracts.business_service import BusinessService, BusinessServiceStatus
from reliability.idempotency_contract import IdempotencyStore

CANON_BUSINESS_SERVICE_LIFECYCLE_OWNER = True


class BusinessServiceRegistry:
    def __init__(self, *, event_store: Any, idempotency_store: IdempotencyStore) -> None:
        self._projector = BusinessServiceProjector(event_store)
        self._writer = EventFactLifecycleWriter(
            event_store=event_store, idempotency_store=idempotency_store,
            namespace="business_service_fact", source="business_service_registry", id_prefix="business-service",
        )

    @staticmethod
    def _time(value: int | None) -> int:
        return int(time.time() * 1000) if value is None else max(0, int(value))

    def create(self, *, tenant_id: str, business_id: str, service_id: str, idempotency_key: str, name: str | None = None, category: str | None = None, occurred_at_ms: int | None = None, event_metadata: dict[str, object] | None = None) -> BusinessService:
        when = self._time(occurred_at_ms)
        candidate = BusinessService(
            service_id=service_id, tenant_id=tenant_id, business_id=business_id,
            name=name, category=category, created_at_ms=when, updated_at_ms=when,
        )
        payload = {"name": candidate.name, "category": candidate.category}
        try:
            current = self._projector.get(tenant_id=tenant_id, business_id=business_id, service_id=service_id)
        except LookupError:
            current = None
        if current is not None:
            if current.name != candidate.name or current.category != candidate.category:
                raise ValueError("business service already exists with different identity metadata")
            self._writer.repair_existing(
                tenant_id=tenant_id, business_id=business_id, entity_id=service_id,
                operation="create", idempotency_key=idempotency_key, fact_type=BUSINESS_SERVICE_CREATED, payload=payload,
                event_metadata=event_metadata,
            )
            return current
        self._writer.append_once(
            tenant_id=tenant_id, business_id=business_id, entity_id=service_id,
            operation="create", idempotency_key=idempotency_key, fact_type=BUSINESS_SERVICE_CREATED,
            payload=payload, occurred_at_ms=when, event_metadata=event_metadata,
        )
        return self._projector.get(tenant_id=tenant_id, business_id=business_id, service_id=service_id)

    def update(self, *, tenant_id: str, business_id: str, service_id: str, idempotency_key: str, name: str | None = None, category: str | None = None, occurred_at_ms: int | None = None, event_metadata: dict[str, object] | None = None) -> BusinessService:
        current = self._projector.get(tenant_id=tenant_id, business_id=business_id, service_id=service_id)
        if current.status is BusinessServiceStatus.ARCHIVED:
            raise ValueError("archived business service cannot be updated")
        when = max(current.updated_at_ms, self._time(occurred_at_ms))
        candidate = BusinessService(
            service_id=current.service_id, tenant_id=current.tenant_id, business_id=current.business_id,
            name=current.name if name is None else name, category=current.category if category is None else category,
            created_at_ms=current.created_at_ms, updated_at_ms=when,
        )
        payload = {"name": candidate.name, "category": candidate.category}
        if candidate.name == current.name and candidate.category == current.category:
            self._writer.repair_existing(
                tenant_id=tenant_id, business_id=business_id, entity_id=service_id,
                operation="update", idempotency_key=idempotency_key, fact_type=BUSINESS_SERVICE_UPDATED, payload=payload,
                event_metadata=event_metadata,
            )
            return current
        self._writer.append_once(
            tenant_id=tenant_id, business_id=business_id, entity_id=service_id,
            operation="update", idempotency_key=idempotency_key, fact_type=BUSINESS_SERVICE_UPDATED,
            payload=payload, occurred_at_ms=when, event_metadata=event_metadata,
        )
        return self._projector.get(tenant_id=tenant_id, business_id=business_id, service_id=service_id)

    def archive(self, *, tenant_id: str, business_id: str, service_id: str, idempotency_key: str, occurred_at_ms: int | None = None, event_metadata: dict[str, object] | None = None) -> BusinessService:
        current = self._projector.get(tenant_id=tenant_id, business_id=business_id, service_id=service_id)
        if current.status is BusinessServiceStatus.ARCHIVED:
            self._writer.repair_existing(
                tenant_id=tenant_id, business_id=business_id, entity_id=service_id,
                operation="archive", idempotency_key=idempotency_key, fact_type=BUSINESS_SERVICE_ARCHIVED, payload={},
                event_metadata=event_metadata,
            )
            return current
        when = max(current.updated_at_ms, self._time(occurred_at_ms))
        self._writer.append_once(
            tenant_id=tenant_id, business_id=business_id, entity_id=service_id,
            operation="archive", idempotency_key=idempotency_key, fact_type=BUSINESS_SERVICE_ARCHIVED,
            payload={}, occurred_at_ms=when, event_metadata=event_metadata,
        )
        return self._projector.get(tenant_id=tenant_id, business_id=business_id, service_id=service_id)

    def get(self, *, tenant_id: str, business_id: str, service_id: str) -> BusinessService:
        return self._projector.get(tenant_id=tenant_id, business_id=business_id, service_id=service_id)

    def list_for_business(self, *, tenant_id: str, business_id: str) -> tuple[BusinessService, ...]:
        return self._projector.list_for_business(tenant_id=tenant_id, business_id=business_id)


__all__ = ["BusinessServiceRegistry", "CANON_BUSINESS_SERVICE_LIFECYCLE_OWNER"]

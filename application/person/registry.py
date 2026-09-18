from __future__ import annotations

import time
from typing import Any

from application.ontology import EventFactLifecycleWriter
from application.person.projector import PERSON_ARCHIVED, PERSON_CREATED, PersonProjector
from contracts.person import Person, PersonStatus
from reliability.idempotency_contract import IdempotencyStore

CANON_PERSON_LIFECYCLE_OWNER = True


class PersonRegistry:
    """Single PII-minimal Person lifecycle writer over canonical EventStore."""

    def __init__(self, *, event_store: Any, idempotency_store: IdempotencyStore) -> None:
        self._projector = PersonProjector(event_store)
        self._writer = EventFactLifecycleWriter(
            event_store=event_store, idempotency_store=idempotency_store, namespace="person_fact", source="person_registry", id_prefix="person"
        )

    @staticmethod
    def _time(value: int | None) -> int:
        return int(time.time() * 1000) if value is None else max(0, int(value))

    def create(self, *, tenant_id: str, business_id: str, person_id: str, idempotency_key: str, occurred_at_ms: int | None = None, event_metadata: dict[str, object] | None = None) -> Person:
        when = self._time(occurred_at_ms)
        candidate = Person(person_id=person_id, tenant_id=tenant_id, business_id=business_id, created_at_ms=when, updated_at_ms=when)
        try:
            current = self._projector.get(tenant_id=candidate.tenant_id, business_id=candidate.business_id, person_id=candidate.person_id)
        except LookupError:
            current = None
        if current is not None:
            self._writer.repair_existing(tenant_id=tenant_id, business_id=business_id, entity_id=person_id, operation="create", idempotency_key=idempotency_key, fact_type=PERSON_CREATED, payload={}, event_metadata=event_metadata)
            return current
        self._writer.append_once(tenant_id=tenant_id, business_id=business_id, entity_id=person_id, operation="create", idempotency_key=idempotency_key, fact_type=PERSON_CREATED, payload={}, occurred_at_ms=when, event_metadata=event_metadata)
        return self._projector.get(tenant_id=tenant_id, business_id=business_id, person_id=person_id)

    def archive(self, *, tenant_id: str, business_id: str, person_id: str, idempotency_key: str, occurred_at_ms: int | None = None, event_metadata: dict[str, object] | None = None) -> Person:
        current = self._projector.get(tenant_id=tenant_id, business_id=business_id, person_id=person_id)
        if current.status is PersonStatus.ARCHIVED:
            self._writer.repair_existing(tenant_id=tenant_id, business_id=business_id, entity_id=person_id, operation="archive", idempotency_key=idempotency_key, fact_type=PERSON_ARCHIVED, payload={}, event_metadata=event_metadata)
            return current
        when = max(current.updated_at_ms, self._time(occurred_at_ms))
        self._writer.append_once(tenant_id=tenant_id, business_id=business_id, entity_id=person_id, operation="archive", idempotency_key=idempotency_key, fact_type=PERSON_ARCHIVED, payload={}, occurred_at_ms=when, event_metadata=event_metadata)
        return self._projector.get(tenant_id=tenant_id, business_id=business_id, person_id=person_id)

    def get(self, *, tenant_id: str, business_id: str, person_id: str) -> Person:
        return self._projector.get(tenant_id=tenant_id, business_id=business_id, person_id=person_id)

    def list_for_business(self, *, tenant_id: str, business_id: str) -> tuple[Person, ...]:
        return self._projector.list_for_business(tenant_id=tenant_id, business_id=business_id)


__all__ = ["CANON_PERSON_LIFECYCLE_OWNER", "PersonRegistry"]

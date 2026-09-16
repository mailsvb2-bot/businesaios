from __future__ import annotations

import time
from typing import Any

from application.lead.facts import LEAD_ARCHIVED, LEAD_CREATED, LEAD_UPDATED
from application.lead.projector import LeadProjector
from application.ontology import EventFactLifecycleWriter
from contracts.lead import Lead, LeadLifecycleStatus
from reliability.idempotency_contract import IdempotencyStore

CANON_LEAD_LIFECYCLE_OWNER = True


class LeadRegistry:
    """Single PII-minimal Lead lifecycle writer over the canonical EventStore."""

    def __init__(self, *, event_store: Any, idempotency_store: IdempotencyStore) -> None:
        self._projector = LeadProjector(event_store)
        self._writer = EventFactLifecycleWriter(
            event_store=event_store, idempotency_store=idempotency_store,
            namespace="lead_fact", source="lead_registry", id_prefix="lead",
        )

    @staticmethod
    def _time(value: int | None) -> int:
        return int(time.time() * 1000) if value is None else max(0, int(value))

    @staticmethod
    def _state_token(lead: Lead) -> str:
        return "|".join((lead.lifecycle_status.value, str(lead.updated_at_ms), lead.source or "", lead.status or ""))

    def create(
        self, *, tenant_id: str, business_id: str, lead_id: str, idempotency_key: str,
        source: str | None = None, status: str | None = None, occurred_at_ms: int | None = None,
    ) -> Lead:
        when = self._time(occurred_at_ms)
        candidate = Lead(
            lead_id=lead_id, tenant_id=tenant_id, business_id=business_id,
            source=source, status=status, created_at_ms=when, updated_at_ms=when,
        )
        payload = {"source": candidate.source, "status": candidate.status}
        try:
            current = self._projector.get(tenant_id=tenant_id, business_id=business_id, lead_id=lead_id)
        except LookupError:
            current = None
        if current is not None:
            if current.source != candidate.source or current.status != candidate.status:
                raise ValueError("lead already exists with different identity metadata")
            self._writer.repair_existing(
                tenant_id=tenant_id, business_id=business_id, entity_id=lead_id,
                operation="create", idempotency_key=idempotency_key, fact_type=LEAD_CREATED, payload=payload,
            )
            return current
        self._writer.append_once(
            tenant_id=tenant_id, business_id=business_id, entity_id=lead_id,
            operation="create", idempotency_key=idempotency_key, fact_type=LEAD_CREATED,
            payload=payload, occurred_at_ms=when,
        )
        return self._projector.get(tenant_id=tenant_id, business_id=business_id, lead_id=lead_id)

    def update(
        self, *, tenant_id: str, business_id: str, lead_id: str, idempotency_key: str,
        source: str | None = None, status: str | None = None, occurred_at_ms: int | None = None,
    ) -> Lead:
        current = self._projector.get(tenant_id=tenant_id, business_id=business_id, lead_id=lead_id)
        if current.lifecycle_status is LeadLifecycleStatus.ARCHIVED:
            raise ValueError("archived lead cannot be updated")
        when = max(current.updated_at_ms, self._time(occurred_at_ms))
        candidate = Lead(
            lead_id=current.lead_id, tenant_id=current.tenant_id, business_id=current.business_id,
            source=current.source if source is None else source,
            status=current.status if status is None else status,
            created_at_ms=current.created_at_ms, updated_at_ms=when,
        )
        if current.source is not None and candidate.source != current.source:
            raise ValueError("lead source cannot be rewritten")
        payload = {"source": candidate.source, "status": candidate.status}
        if candidate.source == current.source and candidate.status == current.status:
            return current
        self._writer.append_transition_once(
            tenant_id=tenant_id, business_id=business_id, entity_id=lead_id,
            expected_state_token=self._state_token(current), operation="update",
            idempotency_key=idempotency_key, fact_type=LEAD_UPDATED, payload=payload,
            occurred_at_ms=when,
        )
        return self._projector.get(tenant_id=tenant_id, business_id=business_id, lead_id=lead_id)

    def archive(
        self, *, tenant_id: str, business_id: str, lead_id: str, idempotency_key: str,
        occurred_at_ms: int | None = None,
    ) -> Lead:
        current = self._projector.get(tenant_id=tenant_id, business_id=business_id, lead_id=lead_id)
        if current.lifecycle_status is LeadLifecycleStatus.ARCHIVED:
            return current
        when = max(current.updated_at_ms, self._time(occurred_at_ms))
        self._writer.append_transition_once(
            tenant_id=tenant_id, business_id=business_id, entity_id=lead_id,
            expected_state_token=self._state_token(current), operation="archive",
            idempotency_key=idempotency_key, fact_type=LEAD_ARCHIVED, payload={}, occurred_at_ms=when,
        )
        return self._projector.get(tenant_id=tenant_id, business_id=business_id, lead_id=lead_id)

    def get(self, *, tenant_id: str, business_id: str, lead_id: str) -> Lead:
        return self._projector.get(tenant_id=tenant_id, business_id=business_id, lead_id=lead_id)

    def list_for_business(self, *, tenant_id: str, business_id: str) -> tuple[Lead, ...]:
        return self._projector.list_for_business(tenant_id=tenant_id, business_id=business_id)


__all__ = ["CANON_LEAD_LIFECYCLE_OWNER", "LeadRegistry"]

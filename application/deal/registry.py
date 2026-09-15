from __future__ import annotations

import time
from typing import Any

from application.deal.facts import DEAL_ARCHIVED, DEAL_CREATED, DEAL_UPDATED
from application.deal.projector import DealProjector
from application.ontology import EventFactLifecycleWriter
from contracts.deal import Deal, DealLifecycleStatus
from reliability.idempotency_contract import IdempotencyStore

CANON_DEAL_LIFECYCLE_OWNER = True


class DealRegistry:
    """Single PII-free Deal lifecycle writer over the canonical EventStore."""

    def __init__(self, *, event_store: Any, idempotency_store: IdempotencyStore) -> None:
        self._projector = DealProjector(event_store)
        self._writer = EventFactLifecycleWriter(
            event_store=event_store, idempotency_store=idempotency_store,
            namespace="deal_fact", source="deal_registry", id_prefix="deal",
        )

    @staticmethod
    def _time(value: int | None) -> int:
        return int(time.time() * 1000) if value is None else max(0, int(value))

    @staticmethod
    def _state_token(deal: Deal) -> str:
        return "|".join((
            deal.lifecycle_status.value, str(deal.updated_at_ms), deal.pipeline_key or "",
            deal.stage_key or "", "" if deal.amount_minor is None else str(deal.amount_minor), deal.currency or "",
        ))

    @staticmethod
    def _payload(deal: Deal) -> dict[str, object]:
        return {
            "pipeline_key": deal.pipeline_key,
            "stage_key": deal.stage_key,
            "amount_minor": deal.amount_minor,
            "currency": deal.currency,
        }

    def create(
        self, *, tenant_id: str, business_id: str, deal_id: str, idempotency_key: str,
        pipeline_key: str | None = None, stage_key: str | None = None,
        amount_minor: int | None = None, currency: str | None = None,
        occurred_at_ms: int | None = None,
    ) -> Deal:
        when = self._time(occurred_at_ms)
        candidate = Deal(
            deal_id=deal_id, tenant_id=tenant_id, business_id=business_id,
            pipeline_key=pipeline_key, stage_key=stage_key, amount_minor=amount_minor, currency=currency,
            created_at_ms=when, updated_at_ms=when,
        )
        payload = self._payload(candidate)
        try:
            current = self._projector.get(tenant_id=tenant_id, business_id=business_id, deal_id=deal_id)
        except LookupError:
            current = None
        if current is not None:
            if self._payload(current) != payload:
                raise ValueError("deal already exists with different identity metadata")
            self._writer.repair_existing(
                tenant_id=tenant_id, business_id=business_id, entity_id=deal_id,
                operation="create", idempotency_key=idempotency_key, fact_type=DEAL_CREATED, payload=payload,
            )
            return current
        self._writer.append_once(
            tenant_id=tenant_id, business_id=business_id, entity_id=deal_id,
            operation="create", idempotency_key=idempotency_key, fact_type=DEAL_CREATED,
            payload=payload, occurred_at_ms=when,
        )
        return self._projector.get(tenant_id=tenant_id, business_id=business_id, deal_id=deal_id)

    def update(
        self, *, tenant_id: str, business_id: str, deal_id: str, idempotency_key: str,
        pipeline_key: str | None = None, stage_key: str | None = None,
        amount_minor: int | None = None, currency: str | None = None,
        occurred_at_ms: int | None = None,
    ) -> Deal:
        current = self._projector.get(tenant_id=tenant_id, business_id=business_id, deal_id=deal_id)
        if current.lifecycle_status is DealLifecycleStatus.ARCHIVED:
            raise ValueError("archived deal cannot be updated")
        when = max(current.updated_at_ms, self._time(occurred_at_ms))
        candidate = Deal(
            deal_id=current.deal_id, tenant_id=current.tenant_id, business_id=current.business_id,
            pipeline_key=current.pipeline_key if pipeline_key is None else pipeline_key,
            stage_key=current.stage_key if stage_key is None else stage_key,
            amount_minor=current.amount_minor if amount_minor is None else amount_minor,
            currency=current.currency if currency is None else currency,
            created_at_ms=current.created_at_ms, updated_at_ms=when,
        )
        if current.pipeline_key is not None and candidate.pipeline_key != current.pipeline_key:
            raise ValueError("deal pipeline cannot be rewritten")
        if current.currency is not None and candidate.currency != current.currency:
            raise ValueError("deal currency cannot be rewritten")
        payload = self._payload(candidate)
        if payload == self._payload(current):
            return current
        self._writer.append_transition_once(
            tenant_id=tenant_id, business_id=business_id, entity_id=deal_id,
            expected_state_token=self._state_token(current), operation="update",
            idempotency_key=idempotency_key, fact_type=DEAL_UPDATED, payload=payload,
            occurred_at_ms=when,
        )
        return self._projector.get(tenant_id=tenant_id, business_id=business_id, deal_id=deal_id)

    def archive(
        self, *, tenant_id: str, business_id: str, deal_id: str, idempotency_key: str,
        occurred_at_ms: int | None = None,
    ) -> Deal:
        current = self._projector.get(tenant_id=tenant_id, business_id=business_id, deal_id=deal_id)
        if current.lifecycle_status is DealLifecycleStatus.ARCHIVED:
            return current
        when = max(current.updated_at_ms, self._time(occurred_at_ms))
        self._writer.append_transition_once(
            tenant_id=tenant_id, business_id=business_id, entity_id=deal_id,
            expected_state_token=self._state_token(current), operation="archive",
            idempotency_key=idempotency_key, fact_type=DEAL_ARCHIVED, payload={}, occurred_at_ms=when,
        )
        return self._projector.get(tenant_id=tenant_id, business_id=business_id, deal_id=deal_id)

    def get(self, *, tenant_id: str, business_id: str, deal_id: str) -> Deal:
        return self._projector.get(tenant_id=tenant_id, business_id=business_id, deal_id=deal_id)

    def list_for_business(self, *, tenant_id: str, business_id: str) -> tuple[Deal, ...]:
        return self._projector.list_for_business(tenant_id=tenant_id, business_id=business_id)


__all__ = ["CANON_DEAL_LIFECYCLE_OWNER", "DealRegistry"]

from __future__ import annotations

import time
from dataclasses import replace
from typing import Any

from application.ontology import EventFactLifecycleWriter
from contracts.deal import Deal, DealLifecycleStatus, DealNotFound
from contracts.event_store import BUSINESS_FACT_EVENT_TYPE
from reliability.idempotency_contract import IdempotencyStore

DEAL_CREATED = "deal.created"
DEAL_UPDATED = "deal.updated"
DEAL_ARCHIVED = "deal.archived"
DEAL_FACT_TYPES = frozenset({DEAL_CREATED, DEAL_UPDATED, DEAL_ARCHIVED})
CANON_DEAL_FACT_VOCABULARY = True
CANON_DEAL_PROJECTOR = True
CANON_DEAL_LIFECYCLE_OWNER = True


class DealHistoryInvariantViolation(RuntimeError):
    pass


class DealProjector:
    def __init__(self, event_store: Any) -> None:
        self._events = event_store

    def _facts(self, *, tenant_id: str, business_id: str, deal_id: str | None = None) -> list[dict[str, object]]:
        rows: list[dict[str, object]] = []
        for append_order, event in enumerate(
            self._events.iter_events(tenant_id=str(tenant_id), start_ms=0, event_type=BUSINESS_FACT_EVENT_TYPE)
        ):
            envelope = dict(event.get("payload") or {})
            if str(envelope.get("business_id") or "") != str(business_id):
                continue
            fact_type = str(envelope.get("fact_type") or "")
            entity_id = str(envelope.get("entity_id") or "")
            if fact_type not in DEAL_FACT_TYPES or (deal_id is not None and entity_id != str(deal_id)):
                continue
            rows.append({
                "fact_id": str(event.get("event_id") or ""),
                "fact_type": fact_type,
                "entity_id": entity_id,
                "event_time_ms": int(envelope.get("event_time_ms") or event.get("timestamp_ms") or 0),
                "observed_at_ms": int(envelope.get("observed_at_ms") or event.get("timestamp_ms") or 0),
                "append_order": append_order,
                "payload": dict(envelope.get("payload") or {}),
            })
        rows.sort(key=lambda row: (row["event_time_ms"], row["observed_at_ms"], row["append_order"], row["fact_id"]))
        return rows

    def get(self, *, tenant_id: str, business_id: str, deal_id: str) -> Deal:
        facts = self._facts(tenant_id=tenant_id, business_id=business_id, deal_id=deal_id)
        if not facts:
            raise DealNotFound(f"deal not found: {deal_id}")
        created_rows = [row for row in facts if row["fact_type"] == DEAL_CREATED]
        if len(created_rows) != 1 or facts[0] is not created_rows[0]:
            raise DealHistoryInvariantViolation("deal history must begin with exactly one create fact")
        created = created_rows[0]
        payload = dict(created["payload"])
        deal = Deal(
            deal_id=str(deal_id), tenant_id=str(tenant_id), business_id=str(business_id),
            pipeline_key=payload.get("pipeline_key"), stage_key=payload.get("stage_key"),
            amount_minor=payload.get("amount_minor"), currency=payload.get("currency"),
            created_at_ms=int(created["event_time_ms"]), updated_at_ms=int(created["event_time_ms"]),
        )
        for row in facts[1:]:
            if deal.lifecycle_status is DealLifecycleStatus.ARCHIVED:
                raise DealHistoryInvariantViolation("deal history continues after archive")
            when = int(row["event_time_ms"])
            if row["fact_type"] == DEAL_UPDATED:
                update = dict(row["payload"])
                next_pipeline = update.get("pipeline_key", deal.pipeline_key)
                next_currency = update.get("currency", deal.currency)
                if deal.pipeline_key is not None and next_pipeline != deal.pipeline_key:
                    raise DealHistoryInvariantViolation("deal pipeline cannot be rewritten")
                if deal.currency is not None and next_currency != deal.currency:
                    raise DealHistoryInvariantViolation("deal currency cannot be rewritten")
                deal = replace(
                    deal,
                    pipeline_key=next_pipeline,
                    stage_key=update.get("stage_key", deal.stage_key),
                    amount_minor=update.get("amount_minor", deal.amount_minor),
                    currency=next_currency,
                    updated_at_ms=max(deal.updated_at_ms, when),
                )
            elif row["fact_type"] == DEAL_ARCHIVED:
                deal = replace(
                    deal, lifecycle_status=DealLifecycleStatus.ARCHIVED,
                    updated_at_ms=max(deal.updated_at_ms, when), archived_at_ms=when,
                )
        return deal

    def list_for_business(self, *, tenant_id: str, business_id: str) -> tuple[Deal, ...]:
        ids = sorted({str(row["entity_id"]) for row in self._facts(tenant_id=tenant_id, business_id=business_id)})
        return tuple(self.get(tenant_id=tenant_id, business_id=business_id, deal_id=value) for value in ids)


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


__all__ = [
    "CANON_DEAL_FACT_VOCABULARY",
    "CANON_DEAL_LIFECYCLE_OWNER",
    "CANON_DEAL_PROJECTOR",
    "DEAL_ARCHIVED",
    "DEAL_CREATED",
    "DEAL_FACT_TYPES",
    "DEAL_UPDATED",
    "DealHistoryInvariantViolation",
    "DealProjector",
    "DealRegistry",
]

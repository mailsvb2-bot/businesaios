from __future__ import annotations

import time
from dataclasses import replace
from typing import Any

from application.ontology import EventFactLifecycleWriter
from contracts.event_store import BUSINESS_FACT_EVENT_TYPE
from contracts.opportunity import Opportunity, OpportunityLifecycleStatus, OpportunityNotFound
from reliability.idempotency_contract import IdempotencyStore

OPPORTUNITY_CREATED = "opportunity.created"
OPPORTUNITY_UPDATED = "opportunity.updated"
OPPORTUNITY_ARCHIVED = "opportunity.archived"
OPPORTUNITY_FACT_TYPES = frozenset({OPPORTUNITY_CREATED, OPPORTUNITY_UPDATED, OPPORTUNITY_ARCHIVED})
CANON_OPPORTUNITY_PROJECTOR = True
CANON_OPPORTUNITY_LIFECYCLE_OWNER = True


class OpportunityHistoryInvariantViolation(RuntimeError):
    pass


class OpportunityProjector:
    def __init__(self, event_store: Any) -> None:
        self._events = event_store

    def _facts(self, *, tenant_id: str, business_id: str, opportunity_id: str | None = None) -> list[dict[str, object]]:
        rows: list[dict[str, object]] = []
        for append_order, event in enumerate(
            self._events.iter_events(tenant_id=str(tenant_id), start_ms=0, event_type=BUSINESS_FACT_EVENT_TYPE)
        ):
            envelope = dict(event.get("payload") or {})
            if str(envelope.get("business_id") or "") != str(business_id):
                continue
            fact_type = str(envelope.get("fact_type") or "")
            entity_id = str(envelope.get("entity_id") or "")
            if fact_type not in OPPORTUNITY_FACT_TYPES or (opportunity_id is not None and entity_id != str(opportunity_id)):
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

    def get(self, *, tenant_id: str, business_id: str, opportunity_id: str) -> Opportunity:
        facts = self._facts(tenant_id=tenant_id, business_id=business_id, opportunity_id=opportunity_id)
        if not facts:
            raise OpportunityNotFound(f"opportunity not found: {opportunity_id}")
        created_rows = [row for row in facts if row["fact_type"] == OPPORTUNITY_CREATED]
        if len(created_rows) != 1 or facts[0] is not created_rows[0]:
            raise OpportunityHistoryInvariantViolation("opportunity history must begin with exactly one create fact")
        created = created_rows[0]
        payload = dict(created["payload"])
        opportunity = Opportunity(
            opportunity_id=str(opportunity_id), tenant_id=str(tenant_id), business_id=str(business_id),
            source_kind=payload.get("source_kind"), stage_key=payload.get("stage_key"),
            expected_value_minor=payload.get("expected_value_minor"), currency=payload.get("currency"),
            created_at_ms=int(created["event_time_ms"]), updated_at_ms=int(created["event_time_ms"]),
        )
        for row in facts[1:]:
            if opportunity.lifecycle_status is OpportunityLifecycleStatus.ARCHIVED:
                raise OpportunityHistoryInvariantViolation("opportunity history continues after archive")
            when = int(row["event_time_ms"])
            if row["fact_type"] == OPPORTUNITY_UPDATED:
                update = dict(row["payload"])
                next_source = update.get("source_kind", opportunity.source_kind)
                next_currency = update.get("currency", opportunity.currency)
                if opportunity.source_kind is not None and next_source != opportunity.source_kind:
                    raise OpportunityHistoryInvariantViolation("opportunity source cannot be rewritten")
                if opportunity.currency is not None and next_currency != opportunity.currency:
                    raise OpportunityHistoryInvariantViolation("opportunity currency cannot be rewritten")
                opportunity = replace(
                    opportunity,
                    source_kind=next_source,
                    stage_key=update.get("stage_key", opportunity.stage_key),
                    expected_value_minor=update.get("expected_value_minor", opportunity.expected_value_minor),
                    currency=next_currency,
                    updated_at_ms=max(opportunity.updated_at_ms, when),
                )
            elif row["fact_type"] == OPPORTUNITY_ARCHIVED:
                opportunity = replace(
                    opportunity, lifecycle_status=OpportunityLifecycleStatus.ARCHIVED,
                    updated_at_ms=max(opportunity.updated_at_ms, when), archived_at_ms=when,
                )
        return opportunity

    def list_for_business(self, *, tenant_id: str, business_id: str) -> tuple[Opportunity, ...]:
        ids = sorted({str(row["entity_id"]) for row in self._facts(tenant_id=tenant_id, business_id=business_id)})
        return tuple(self.get(tenant_id=tenant_id, business_id=business_id, opportunity_id=value) for value in ids)



class OpportunityRegistry:
    def __init__(self, *, event_store: Any, idempotency_store: IdempotencyStore) -> None:
        self._projector = OpportunityProjector(event_store)
        self._writer = EventFactLifecycleWriter(
            event_store=event_store, idempotency_store=idempotency_store,
            namespace="opportunity_fact", source="opportunity_registry", id_prefix="opportunity",
        )

    @staticmethod
    def _time(value: int | None) -> int:
        return int(time.time() * 1000) if value is None else max(0, int(value))

    @staticmethod
    def _payload(opportunity: Opportunity) -> dict[str, object]:
        return {
            "source_kind": opportunity.source_kind,
            "stage_key": opportunity.stage_key,
            "expected_value_minor": opportunity.expected_value_minor,
            "currency": opportunity.currency,
        }

    @staticmethod
    def _state_token(opportunity: Opportunity) -> str:
        return "|".join((
            opportunity.lifecycle_status.value, str(opportunity.updated_at_ms), opportunity.source_kind or "",
            opportunity.stage_key or "", "" if opportunity.expected_value_minor is None else str(opportunity.expected_value_minor),
            opportunity.currency or "",
        ))

    def create(self, *, tenant_id: str, business_id: str, opportunity_id: str, idempotency_key: str,
               source_kind: str | None = None, stage_key: str | None = None,
               expected_value_minor: int | None = None, currency: str | None = None,
               occurred_at_ms: int | None = None) -> Opportunity:
        when = self._time(occurred_at_ms)
        candidate = Opportunity(
            opportunity_id=opportunity_id, tenant_id=tenant_id, business_id=business_id,
            source_kind=source_kind, stage_key=stage_key, expected_value_minor=expected_value_minor,
            currency=currency, created_at_ms=when, updated_at_ms=when,
        )
        payload = self._payload(candidate)
        try:
            current = self._projector.get(tenant_id=tenant_id, business_id=business_id, opportunity_id=opportunity_id)
        except LookupError:
            current = None
        if current is not None:
            if self._payload(current) != payload:
                raise ValueError("opportunity already exists with different identity metadata")
            self._writer.repair_existing(
                tenant_id=tenant_id, business_id=business_id, entity_id=opportunity_id,
                operation="create", idempotency_key=idempotency_key, fact_type=OPPORTUNITY_CREATED, payload=payload,
            )
            return current
        self._writer.append_once(
            tenant_id=tenant_id, business_id=business_id, entity_id=opportunity_id,
            operation="create", idempotency_key=idempotency_key, fact_type=OPPORTUNITY_CREATED,
            payload=payload, occurred_at_ms=when,
        )
        return self._projector.get(tenant_id=tenant_id, business_id=business_id, opportunity_id=opportunity_id)

    def update(self, *, tenant_id: str, business_id: str, opportunity_id: str, idempotency_key: str,
               source_kind: str | None = None, stage_key: str | None = None,
               expected_value_minor: int | None = None, currency: str | None = None,
               occurred_at_ms: int | None = None) -> Opportunity:
        current = self._projector.get(tenant_id=tenant_id, business_id=business_id, opportunity_id=opportunity_id)
        if current.lifecycle_status is OpportunityLifecycleStatus.ARCHIVED:
            raise ValueError("archived opportunity cannot be updated")
        when = max(current.updated_at_ms, self._time(occurred_at_ms))
        candidate = Opportunity(
            opportunity_id=current.opportunity_id, tenant_id=current.tenant_id, business_id=current.business_id,
            source_kind=current.source_kind if source_kind is None else source_kind,
            stage_key=current.stage_key if stage_key is None else stage_key,
            expected_value_minor=current.expected_value_minor if expected_value_minor is None else expected_value_minor,
            currency=current.currency if currency is None else currency,
            created_at_ms=current.created_at_ms, updated_at_ms=when,
        )
        if current.source_kind is not None and candidate.source_kind != current.source_kind:
            raise ValueError("opportunity source cannot be rewritten")
        if current.currency is not None and candidate.currency != current.currency:
            raise ValueError("opportunity currency cannot be rewritten")
        payload = self._payload(candidate)
        if payload == self._payload(current):
            return current
        self._writer.append_transition_once(
            tenant_id=tenant_id, business_id=business_id, entity_id=opportunity_id,
            expected_state_token=self._state_token(current), operation="update", idempotency_key=idempotency_key,
            fact_type=OPPORTUNITY_UPDATED, payload=payload, occurred_at_ms=when,
        )
        return self._projector.get(tenant_id=tenant_id, business_id=business_id, opportunity_id=opportunity_id)

    def archive(self, *, tenant_id: str, business_id: str, opportunity_id: str, idempotency_key: str,
                occurred_at_ms: int | None = None) -> Opportunity:
        current = self._projector.get(tenant_id=tenant_id, business_id=business_id, opportunity_id=opportunity_id)
        if current.lifecycle_status is OpportunityLifecycleStatus.ARCHIVED:
            return current
        when = max(current.updated_at_ms, self._time(occurred_at_ms))
        self._writer.append_transition_once(
            tenant_id=tenant_id, business_id=business_id, entity_id=opportunity_id,
            expected_state_token=self._state_token(current), operation="archive", idempotency_key=idempotency_key,
            fact_type=OPPORTUNITY_ARCHIVED, payload={}, occurred_at_ms=when,
        )
        return self._projector.get(tenant_id=tenant_id, business_id=business_id, opportunity_id=opportunity_id)

    def get(self, *, tenant_id: str, business_id: str, opportunity_id: str) -> Opportunity:
        return self._projector.get(tenant_id=tenant_id, business_id=business_id, opportunity_id=opportunity_id)

    def list_for_business(self, *, tenant_id: str, business_id: str) -> tuple[Opportunity, ...]:
        return self._projector.list_for_business(tenant_id=tenant_id, business_id=business_id)



__all__ = [
    "CANON_OPPORTUNITY_LIFECYCLE_OWNER",
    "CANON_OPPORTUNITY_PROJECTOR",
    "OpportunityHistoryInvariantViolation",
    "OpportunityProjector",
    "OpportunityRegistry",
]

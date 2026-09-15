from __future__ import annotations

from dataclasses import replace
from typing import Any

from application.deal.facts import DEAL_ARCHIVED, DEAL_CREATED, DEAL_FACT_TYPES, DEAL_UPDATED
from contracts.deal import Deal, DealLifecycleStatus, DealNotFound
from contracts.event_store import BUSINESS_FACT_EVENT_TYPE

CANON_DEAL_PROJECTOR = True


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


__all__ = ["CANON_DEAL_PROJECTOR", "DealHistoryInvariantViolation", "DealProjector"]

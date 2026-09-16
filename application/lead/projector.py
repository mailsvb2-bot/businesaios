from __future__ import annotations

from dataclasses import replace
from typing import Any

from application.lead.facts import LEAD_ARCHIVED, LEAD_CREATED, LEAD_FACT_TYPES, LEAD_UPDATED
from contracts.event_store import BUSINESS_FACT_EVENT_TYPE
from contracts.lead import Lead, LeadLifecycleStatus, LeadNotFound

CANON_LEAD_PROJECTOR = True


class LeadHistoryInvariantViolation(RuntimeError):
    pass


class LeadProjector:
    def __init__(self, event_store: Any) -> None:
        self._events = event_store

    def _facts(self, *, tenant_id: str, business_id: str, lead_id: str | None = None) -> list[dict[str, object]]:
        rows: list[dict[str, object]] = []
        for append_order, event in enumerate(
            self._events.iter_events(tenant_id=str(tenant_id), start_ms=0, event_type=BUSINESS_FACT_EVENT_TYPE)
        ):
            envelope = dict(event.get("payload") or {})
            if str(envelope.get("business_id") or "") != str(business_id):
                continue
            fact_type = str(envelope.get("fact_type") or "")
            entity_id = str(envelope.get("entity_id") or "")
            if fact_type not in LEAD_FACT_TYPES or (lead_id is not None and entity_id != str(lead_id)):
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

    def get(self, *, tenant_id: str, business_id: str, lead_id: str) -> Lead:
        facts = self._facts(tenant_id=tenant_id, business_id=business_id, lead_id=lead_id)
        if not facts:
            raise LeadNotFound(f"lead not found: {lead_id}")
        created_rows = [row for row in facts if row["fact_type"] == LEAD_CREATED]
        if not created_rows:
            raise LeadNotFound(f"lead not found: {lead_id}")
        if len(created_rows) != 1 or facts[0] is not created_rows[0]:
            raise LeadHistoryInvariantViolation("lead history must begin with exactly one create fact")
        created = created_rows[0]
        payload = dict(created["payload"])
        lead = Lead(
            lead_id=str(lead_id), tenant_id=str(tenant_id), business_id=str(business_id),
            source=payload.get("source"), status=payload.get("status"),
            created_at_ms=int(created["event_time_ms"]), updated_at_ms=int(created["event_time_ms"]),
        )
        for row in facts[1:]:
            if lead.lifecycle_status is LeadLifecycleStatus.ARCHIVED:
                raise LeadHistoryInvariantViolation("lead history continues after archive")
            when = int(row["event_time_ms"])
            if row["fact_type"] == LEAD_UPDATED:
                update = dict(row["payload"])
                next_source = update.get("source", lead.source)
                if lead.source is not None and next_source != lead.source:
                    raise LeadHistoryInvariantViolation("lead source cannot be rewritten")
                lead = replace(
                    lead, source=next_source, status=update.get("status", lead.status),
                    updated_at_ms=max(lead.updated_at_ms, when),
                )
            elif row["fact_type"] == LEAD_ARCHIVED:
                lead = replace(
                    lead, lifecycle_status=LeadLifecycleStatus.ARCHIVED,
                    updated_at_ms=max(lead.updated_at_ms, when), archived_at_ms=when,
                )
        return lead

    def list_for_business(self, *, tenant_id: str, business_id: str) -> tuple[Lead, ...]:
        ids = sorted({str(row["entity_id"]) for row in self._facts(tenant_id=tenant_id, business_id=business_id)})
        return tuple(self.get(tenant_id=tenant_id, business_id=business_id, lead_id=value) for value in ids)


__all__ = ["CANON_LEAD_PROJECTOR", "LeadHistoryInvariantViolation", "LeadProjector"]

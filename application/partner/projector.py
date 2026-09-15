from __future__ import annotations

from dataclasses import replace
from typing import Any

from application.partner.facts import PARTNER_ARCHIVED, PARTNER_CREATED, PARTNER_FACT_TYPES
from contracts.event_store import BUSINESS_FACT_EVENT_TYPE
from contracts.partner import Partner, PartnerNotFound, PartnerPartyKind, PartnerStatus

CANON_PARTNER_PROJECTOR = True


class PartnerProjector:
    def __init__(self, event_store: Any) -> None:
        self._events = event_store

    def _facts(self, *, tenant_id: str, business_id: str, partner_id: str | None = None) -> list[dict[str, object]]:
        rows: list[dict[str, object]] = []
        for append_order, event in enumerate(self._events.iter_events(tenant_id=str(tenant_id), start_ms=0, event_type=BUSINESS_FACT_EVENT_TYPE)):
            envelope = dict(event.get("payload") or {})
            if str(envelope.get("business_id") or "") != str(business_id):
                continue
            fact_type, entity_id = str(envelope.get("fact_type") or ""), str(envelope.get("entity_id") or "")
            if fact_type not in PARTNER_FACT_TYPES or (partner_id is not None and entity_id != str(partner_id)):
                continue
            rows.append({
                "fact_id": str(event.get("event_id") or ""), "fact_type": fact_type, "entity_id": entity_id,
                "event_time_ms": int(envelope.get("event_time_ms") or event.get("timestamp_ms") or 0),
                "observed_at_ms": int(envelope.get("observed_at_ms") or event.get("timestamp_ms") or 0),
                "append_order": append_order, "payload": dict(envelope.get("payload") or {}),
            })
        rows.sort(key=lambda row: (row["event_time_ms"], row["observed_at_ms"], row["append_order"], row["fact_id"]))
        return rows

    def get(self, *, tenant_id: str, business_id: str, partner_id: str) -> Partner:
        facts = self._facts(tenant_id=tenant_id, business_id=business_id, partner_id=partner_id)
        created = next((row for row in facts if row["fact_type"] == PARTNER_CREATED), None)
        if created is None:
            raise PartnerNotFound(f"partner not found: {partner_id}")
        payload = dict(created["payload"])
        partner = Partner(
            partner_id=str(partner_id), tenant_id=str(tenant_id), business_id=str(business_id),
            party_kind=PartnerPartyKind(str(payload.get("party_kind") or "")), party_id=str(payload.get("party_id") or ""),
            created_at_ms=int(created["event_time_ms"]), updated_at_ms=int(created["event_time_ms"]),
        )
        for row in facts:
            if row["fact_type"] == PARTNER_ARCHIVED:
                partner = replace(
                    partner, status=PartnerStatus.ARCHIVED,
                    updated_at_ms=max(partner.updated_at_ms, int(row["event_time_ms"])),
                    archived_at_ms=int(row["event_time_ms"]),
                )
        return partner

    def list_for_business(self, *, tenant_id: str, business_id: str) -> tuple[Partner, ...]:
        ids = sorted({str(row["entity_id"]) for row in self._facts(tenant_id=tenant_id, business_id=business_id)})
        return tuple(self.get(tenant_id=tenant_id, business_id=business_id, partner_id=value) for value in ids)


__all__ = ["CANON_PARTNER_PROJECTOR", "PartnerProjector"]

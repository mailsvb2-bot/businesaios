from __future__ import annotations

from dataclasses import replace
from typing import Any

from application.business_service.facts import (
    BUSINESS_SERVICE_ARCHIVED,
    BUSINESS_SERVICE_CREATED,
    BUSINESS_SERVICE_FACT_TYPES,
    BUSINESS_SERVICE_UPDATED,
)
from contracts.business_service import BusinessService, BusinessServiceNotFound, BusinessServiceStatus
from contracts.event_store import BUSINESS_FACT_EVENT_TYPE

CANON_BUSINESS_SERVICE_PROJECTOR = True


class BusinessServiceProjector:
    def __init__(self, event_store: Any) -> None:
        self._events = event_store

    def _facts(self, *, tenant_id: str, business_id: str, service_id: str | None = None) -> list[dict[str, object]]:
        rows: list[dict[str, object]] = []
        for append_order, event in enumerate(self._events.iter_events(tenant_id=str(tenant_id), start_ms=0, event_type=BUSINESS_FACT_EVENT_TYPE)):
            envelope = dict(event.get("payload") or {})
            if str(envelope.get("business_id") or "") != str(business_id):
                continue
            fact_type, entity_id = str(envelope.get("fact_type") or ""), str(envelope.get("entity_id") or "")
            if fact_type not in BUSINESS_SERVICE_FACT_TYPES or (service_id is not None and entity_id != str(service_id)):
                continue
            rows.append({
                "fact_id": str(event.get("event_id") or ""), "fact_type": fact_type, "entity_id": entity_id,
                "event_time_ms": int(envelope.get("event_time_ms") or event.get("timestamp_ms") or 0),
                "observed_at_ms": int(envelope.get("observed_at_ms") or event.get("timestamp_ms") or 0),
                "append_order": append_order, "payload": dict(envelope.get("payload") or {}),
            })
        rows.sort(key=lambda row: (row["event_time_ms"], row["observed_at_ms"], row["append_order"], row["fact_id"]))
        return rows

    def get(self, *, tenant_id: str, business_id: str, service_id: str) -> BusinessService:
        facts = self._facts(tenant_id=tenant_id, business_id=business_id, service_id=service_id)
        created = next((row for row in facts if row["fact_type"] == BUSINESS_SERVICE_CREATED), None)
        if created is None:
            raise BusinessServiceNotFound(f"business service not found: {service_id}")
        payload = dict(created["payload"])
        service = BusinessService(
            service_id=str(service_id), tenant_id=str(tenant_id), business_id=str(business_id),
            name=payload.get("name"), category=payload.get("category"),
            created_at_ms=int(created["event_time_ms"]), updated_at_ms=int(created["event_time_ms"]),
        )
        for row in facts:
            if row["fact_type"] == BUSINESS_SERVICE_UPDATED:
                payload = dict(row["payload"])
                service = replace(
                    service, name=payload.get("name", service.name), category=payload.get("category", service.category),
                    updated_at_ms=max(service.updated_at_ms, int(row["event_time_ms"])),
                )
            elif row["fact_type"] == BUSINESS_SERVICE_ARCHIVED:
                service = replace(
                    service, status=BusinessServiceStatus.ARCHIVED,
                    updated_at_ms=max(service.updated_at_ms, int(row["event_time_ms"])),
                    archived_at_ms=int(row["event_time_ms"]),
                )
        return service

    def list_for_business(self, *, tenant_id: str, business_id: str) -> tuple[BusinessService, ...]:
        ids = sorted({str(row["entity_id"]) for row in self._facts(tenant_id=tenant_id, business_id=business_id)})
        return tuple(self.get(tenant_id=tenant_id, business_id=business_id, service_id=value) for value in ids)


__all__ = ["BusinessServiceProjector", "CANON_BUSINESS_SERVICE_PROJECTOR"]

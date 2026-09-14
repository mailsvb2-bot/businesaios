from __future__ import annotations

from dataclasses import replace
from typing import Any

from application.organization.facts import (
    ORGANIZATION_ARCHIVED,
    ORGANIZATION_CREATED,
    ORGANIZATION_FACT_TYPES,
    ORGANIZATION_UPDATED,
)
from contracts.event_store import BUSINESS_FACT_EVENT_TYPE
from contracts.organization import Organization, OrganizationNotFound, OrganizationStatus

CANON_ORGANIZATION_PROJECTOR = True


class OrganizationProjector:
    """Read-only Organization projection over the canonical EventStore chronology."""

    def __init__(self, event_store: Any) -> None:
        self._events = event_store

    def _facts(self, *, tenant_id: str, business_id: str, organization_id: str | None = None) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for append_order, event in enumerate(
            self._events.iter_events(tenant_id=str(tenant_id), start_ms=0, event_type=BUSINESS_FACT_EVENT_TYPE)
        ):
            envelope = dict(event.get("payload") or {})
            if str(envelope.get("business_id") or "") != str(business_id):
                continue
            fact_type = str(envelope.get("fact_type") or "")
            entity_id = str(envelope.get("entity_id") or "")
            if fact_type not in ORGANIZATION_FACT_TYPES:
                continue
            if organization_id is not None and entity_id != str(organization_id):
                continue
            rows.append(
                {
                    "fact_id": str(event.get("event_id") or ""),
                    "fact_type": fact_type,
                    "entity_id": entity_id,
                    "event_time_ms": int(envelope.get("event_time_ms") or event.get("timestamp_ms") or 0),
                    "observed_at_ms": int(envelope.get("observed_at_ms") or event.get("timestamp_ms") or 0),
                    "append_order": append_order,
                    "payload": dict(envelope.get("payload") or {}),
                }
            )
        rows.sort(key=lambda row: (row["event_time_ms"], row["observed_at_ms"], row["append_order"], row["fact_id"]))
        return rows

    def get(self, *, tenant_id: str, business_id: str, organization_id: str) -> Organization:
        facts = self._facts(tenant_id=tenant_id, business_id=business_id, organization_id=organization_id)
        created = next((row for row in facts if row["fact_type"] == ORGANIZATION_CREATED), None)
        if created is None:
            raise OrganizationNotFound(f"organization not found: {organization_id}")
        payload = created["payload"]
        organization = Organization(
            organization_id=str(organization_id),
            tenant_id=str(tenant_id),
            business_id=str(business_id),
            name=payload.get("name"),
            organization_type=payload.get("organization_type"),
            created_at_ms=created["event_time_ms"],
            updated_at_ms=created["event_time_ms"],
        )
        for row in facts:
            if row is created:
                continue
            if row["fact_type"] == ORGANIZATION_UPDATED:
                update = row["payload"]
                organization = replace(
                    organization,
                    name=update.get("name", organization.name),
                    organization_type=update.get("organization_type", organization.organization_type),
                    updated_at_ms=max(organization.updated_at_ms, row["event_time_ms"]),
                )
            elif row["fact_type"] == ORGANIZATION_ARCHIVED:
                organization = replace(
                    organization,
                    status=OrganizationStatus.ARCHIVED,
                    updated_at_ms=max(organization.updated_at_ms, row["event_time_ms"]),
                    archived_at_ms=row["event_time_ms"],
                )
        return organization

    def list_for_business(self, *, tenant_id: str, business_id: str) -> tuple[Organization, ...]:
        ids = sorted({row["entity_id"] for row in self._facts(tenant_id=tenant_id, business_id=business_id)})
        return tuple(self.get(tenant_id=tenant_id, business_id=business_id, organization_id=value) for value in ids)


__all__ = [
    "CANON_ORGANIZATION_PROJECTOR",
    "ORGANIZATION_ARCHIVED",
    "ORGANIZATION_CREATED",
    "ORGANIZATION_FACT_TYPES",
    "ORGANIZATION_UPDATED",
    "OrganizationProjector",
]

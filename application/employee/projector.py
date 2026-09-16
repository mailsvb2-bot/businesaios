from __future__ import annotations

from dataclasses import replace
from typing import Any

from contracts.employee import Employee, EmployeeNotFound, EmployeeStatus
from contracts.event_store import BUSINESS_FACT_EVENT_TYPE

EMPLOYEE_CREATED = "employee.created"
EMPLOYEE_ARCHIVED = "employee.archived"
EMPLOYEE_FACT_TYPES = frozenset({EMPLOYEE_CREATED, EMPLOYEE_ARCHIVED})

CANON_EMPLOYEE_PROJECTOR = True


class EmployeeProjector:
    """Read-only Employee projection over canonical EventStore facts."""

    def __init__(self, event_store: Any) -> None:
        self._events = event_store

    def _facts(self, *, tenant_id: str, business_id: str, employee_id: str | None = None) -> list[dict[str, object]]:
        rows: list[dict[str, object]] = []
        for append_order, event in enumerate(self._events.iter_events(tenant_id=str(tenant_id), start_ms=0, event_type=BUSINESS_FACT_EVENT_TYPE)):
            envelope = dict(event.get("payload") or {})
            if str(envelope.get("business_id") or "") != str(business_id):
                continue
            fact_type, entity_id = str(envelope.get("fact_type") or ""), str(envelope.get("entity_id") or "")
            if fact_type not in EMPLOYEE_FACT_TYPES or (employee_id is not None and entity_id != str(employee_id)):
                continue
            rows.append({
                "fact_id": str(event.get("event_id") or ""), "fact_type": fact_type, "entity_id": entity_id,
                "event_time_ms": int(envelope.get("event_time_ms") or event.get("timestamp_ms") or 0),
                "observed_at_ms": int(envelope.get("observed_at_ms") or event.get("timestamp_ms") or 0),
                "append_order": append_order, "payload": dict(envelope.get("payload") or {}),
            })
        rows.sort(key=lambda row: (row["event_time_ms"], row["observed_at_ms"], row["append_order"], row["fact_id"]))
        return rows

    def get(self, *, tenant_id: str, business_id: str, employee_id: str) -> Employee:
        facts = self._facts(tenant_id=tenant_id, business_id=business_id, employee_id=employee_id)
        created = next((row for row in facts if row["fact_type"] == EMPLOYEE_CREATED), None)
        if created is None:
            raise EmployeeNotFound(f"employee not found: {employee_id}")
        payload = dict(created["payload"])
        employee = Employee(
            employee_id=str(employee_id), tenant_id=str(tenant_id), business_id=str(business_id),
            person_id=str(payload.get("person_id") or ""), organization_id=str(payload.get("organization_id") or ""),
            created_at_ms=int(created["event_time_ms"]), updated_at_ms=int(created["event_time_ms"]),
        )
        for row in facts:
            if row["fact_type"] == EMPLOYEE_ARCHIVED:
                employee = replace(
                    employee, status=EmployeeStatus.ARCHIVED,
                    updated_at_ms=max(employee.updated_at_ms, int(row["event_time_ms"])),
                    archived_at_ms=int(row["event_time_ms"]),
                )
        return employee

    def list_for_business(self, *, tenant_id: str, business_id: str) -> tuple[Employee, ...]:
        ids = sorted({str(row["entity_id"]) for row in self._facts(tenant_id=tenant_id, business_id=business_id)})
        return tuple(self.get(tenant_id=tenant_id, business_id=business_id, employee_id=value) for value in ids)


__all__ = ["CANON_EMPLOYEE_PROJECTOR", "EmployeeProjector"]

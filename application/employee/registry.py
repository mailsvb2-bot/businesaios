from __future__ import annotations

import time
from typing import Any

from application.employee.facts import EMPLOYEE_ARCHIVED, EMPLOYEE_CREATED
from application.employee.projector import EmployeeProjector
from application.ontology import EventFactLifecycleWriter
from application.organization.projector import OrganizationProjector
from application.person.projector import PersonProjector
from contracts.employee import Employee, EmployeeStatus
from contracts.organization import OrganizationStatus
from contracts.person import PersonStatus
from reliability.idempotency_contract import IdempotencyStore

CANON_EMPLOYEE_LIFECYCLE_OWNER = True


class EmployeeRegistry:
    """Single Employee relationship writer over canonical Person/Organization facts."""

    def __init__(self, *, event_store: Any, idempotency_store: IdempotencyStore) -> None:
        self._projector = EmployeeProjector(event_store)
        self._people = PersonProjector(event_store)
        self._organizations = OrganizationProjector(event_store)
        self._writer = EventFactLifecycleWriter(
            event_store=event_store, idempotency_store=idempotency_store,
            namespace="employee_fact", source="employee_registry", id_prefix="employee",
        )

    @staticmethod
    def _time(value: int | None) -> int:
        return int(time.time() * 1000) if value is None else max(0, int(value))

    def create(
        self, *, tenant_id: str, business_id: str, employee_id: str, person_id: str,
        organization_id: str, idempotency_key: str, occurred_at_ms: int | None = None,
    ) -> Employee:
        person = self._people.get(tenant_id=tenant_id, business_id=business_id, person_id=person_id)
        organization = self._organizations.get(tenant_id=tenant_id, business_id=business_id, organization_id=organization_id)
        if person.status is not PersonStatus.ACTIVE:
            raise ValueError("employee requires active person")
        if organization.status is not OrganizationStatus.ACTIVE:
            raise ValueError("employee requires active organization")
        when = self._time(occurred_at_ms)
        candidate = Employee(
            employee_id=employee_id, tenant_id=tenant_id, business_id=business_id,
            person_id=person.person_id, organization_id=organization.organization_id,
            created_at_ms=when, updated_at_ms=when,
        )
        payload = {"person_id": candidate.person_id, "organization_id": candidate.organization_id}
        try:
            current = self._projector.get(tenant_id=tenant_id, business_id=business_id, employee_id=employee_id)
        except LookupError:
            current = None
        if current is not None:
            if current.person_id != candidate.person_id or current.organization_id != candidate.organization_id:
                raise ValueError("employee already exists with different relationship identity")
            self._writer.repair_existing(
                tenant_id=tenant_id, business_id=business_id, entity_id=employee_id,
                operation="create", idempotency_key=idempotency_key, fact_type=EMPLOYEE_CREATED, payload=payload,
            )
            return current
        self._writer.append_once(
            tenant_id=tenant_id, business_id=business_id, entity_id=employee_id,
            operation="create", idempotency_key=idempotency_key, fact_type=EMPLOYEE_CREATED,
            payload=payload, occurred_at_ms=when,
        )
        return self._projector.get(tenant_id=tenant_id, business_id=business_id, employee_id=employee_id)

    def archive(self, *, tenant_id: str, business_id: str, employee_id: str, idempotency_key: str, occurred_at_ms: int | None = None) -> Employee:
        current = self._projector.get(tenant_id=tenant_id, business_id=business_id, employee_id=employee_id)
        if current.status is EmployeeStatus.ARCHIVED:
            self._writer.repair_existing(
                tenant_id=tenant_id, business_id=business_id, entity_id=employee_id,
                operation="archive", idempotency_key=idempotency_key, fact_type=EMPLOYEE_ARCHIVED, payload={},
            )
            return current
        when = max(current.updated_at_ms, self._time(occurred_at_ms))
        self._writer.append_once(
            tenant_id=tenant_id, business_id=business_id, entity_id=employee_id,
            operation="archive", idempotency_key=idempotency_key, fact_type=EMPLOYEE_ARCHIVED,
            payload={}, occurred_at_ms=when,
        )
        return self._projector.get(tenant_id=tenant_id, business_id=business_id, employee_id=employee_id)

    def get(self, *, tenant_id: str, business_id: str, employee_id: str) -> Employee:
        return self._projector.get(tenant_id=tenant_id, business_id=business_id, employee_id=employee_id)

    def list_for_business(self, *, tenant_id: str, business_id: str) -> tuple[Employee, ...]:
        return self._projector.list_for_business(tenant_id=tenant_id, business_id=business_id)


__all__ = ["CANON_EMPLOYEE_LIFECYCLE_OWNER", "EmployeeRegistry"]

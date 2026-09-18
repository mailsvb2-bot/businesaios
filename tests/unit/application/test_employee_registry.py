from __future__ import annotations

from dataclasses import fields

import pytest

from application.employee import EmployeeProjector, EmployeeRegistry
from contracts.event_store import canonical_business_event_contract
from application.organization import OrganizationRegistry
from application.person import PersonRegistry
from contracts.employee import Employee, EmployeeNotFound, EmployeeStatus
from contracts.organization import OrganizationNotFound
from contracts.person import PersonNotFound
from reliability.idempotency_store import InMemoryIdempotencyStore


class MemoryEventStore:
    def __init__(self) -> None:
        self.events: list[dict] = []

    def append_event(self, event: dict) -> None:
        self.events.append(dict(event))

    def iter_events(self, *, tenant_id: str, start_ms: int, end_ms=None, user_id=None, event_type=None):
        for event in self.events:
            if str(event.get("tenant_id") or "") != str(tenant_id):
                continue
            if int(event.get("timestamp_ms") or 0) < int(start_ms):
                continue
            if end_ms is not None and int(event.get("timestamp_ms") or 0) > int(end_ms):
                continue
            if event_type is not None and str(event.get("event_type") or "") != str(event_type):
                continue
            yield dict(event)

    def count_events(self, *, tenant_id: str, start_ms: int, end_ms: int, user_id=None, event_type=None) -> int:
        return sum(1 for _ in self.iter_events(tenant_id=tenant_id, start_ms=start_ms, end_ms=end_ms, user_id=user_id, event_type=event_type))


def _stack():
    events = MemoryEventStore()
    claims = InMemoryIdempotencyStore()
    organizations = OrganizationRegistry(event_store=events, idempotency_store=claims)
    people = PersonRegistry(event_store=events, idempotency_store=claims)
    employees = EmployeeRegistry(event_store=events, idempotency_store=claims)
    return events, organizations, people, employees


def _seed(organizations, people, *, tenant_id="tenant-1", business_id="business-1"):
    organizations.create(
        tenant_id=tenant_id, business_id=business_id, organization_id="org-1",
        idempotency_key=f"org:{tenant_id}:{business_id}", occurred_at_ms=1,
    )
    people.create(
        tenant_id=tenant_id, business_id=business_id, person_id="person-1",
        idempotency_key=f"person:{tenant_id}:{business_id}", occurred_at_ms=1,
    )


def test_employee_contract_is_pii_minimal_relationship() -> None:
    assert tuple(field.name for field in fields(Employee)) == (
        "employee_id", "tenant_id", "business_id", "person_id", "organization_id",
        "status", "created_at_ms", "updated_at_ms", "archived_at_ms",
    )


def test_employee_requires_existing_person_and_organization() -> None:
    _, organizations, people, employees = _stack()
    with pytest.raises(PersonNotFound):
        employees.create(
            tenant_id="tenant-1", business_id="business-1", employee_id="emp-1",
            person_id="person-1", organization_id="org-1", idempotency_key="emp-1", occurred_at_ms=2,
        )
    people.create(
        tenant_id="tenant-1", business_id="business-1", person_id="person-1",
        idempotency_key="person", occurred_at_ms=1,
    )
    with pytest.raises(OrganizationNotFound):
        employees.create(
            tenant_id="tenant-1", business_id="business-1", employee_id="emp-1",
            person_id="person-1", organization_id="org-1", idempotency_key="emp-1", occurred_at_ms=2,
        )
    organizations.create(
        tenant_id="tenant-1", business_id="business-1", organization_id="org-1",
        idempotency_key="org", occurred_at_ms=1,
    )
    created = employees.create(
        tenant_id="tenant-1", business_id="business-1", employee_id="emp-1",
        person_id="person-1", organization_id="org-1", idempotency_key="emp-1", occurred_at_ms=2,
    )
    assert created.person_id == "person-1"
    assert created.organization_id == "org-1"


def test_employee_lifecycle_is_idempotent_and_scoped() -> None:
    events, organizations, people, employees = _stack()
    _seed(organizations, people)
    created = employees.create(
        tenant_id="tenant-1", business_id="business-1", employee_id="emp-1",
        person_id="person-1", organization_id="org-1", idempotency_key="create", occurred_at_ms=2,
    )
    replay = employees.create(
        tenant_id="tenant-1", business_id="business-1", employee_id="emp-1",
        person_id="person-1", organization_id="org-1", idempotency_key="create", occurred_at_ms=999,
    )
    assert replay == created
    archived = employees.archive(
        tenant_id="tenant-1", business_id="business-1", employee_id="emp-1",
        idempotency_key="archive", occurred_at_ms=3,
    )
    assert archived.status is EmployeeStatus.ARCHIVED
    assert archived.archived_at_ms == 3
    assert len([e for e in events.events if dict(e.get("payload") or {}).get("fact_type", "").startswith("employee.")]) == 2


def test_employee_relationship_identity_cannot_be_rebound() -> None:
    _, organizations, people, employees = _stack()
    _seed(organizations, people)
    people.create(
        tenant_id="tenant-1", business_id="business-1", person_id="person-2",
        idempotency_key="person-2", occurred_at_ms=1,
    )
    employees.create(
        tenant_id="tenant-1", business_id="business-1", employee_id="emp-1",
        person_id="person-1", organization_id="org-1", idempotency_key="create-1", occurred_at_ms=2,
    )
    with pytest.raises(ValueError, match="different relationship identity"):
        employees.create(
            tenant_id="tenant-1", business_id="business-1", employee_id="emp-1",
            person_id="person-2", organization_id="org-1", idempotency_key="create-2", occurred_at_ms=3,
        )


def test_employee_rejects_archived_person_or_organization() -> None:
    _, organizations, people, employees = _stack()
    _seed(organizations, people)
    people.archive(
        tenant_id="tenant-1", business_id="business-1", person_id="person-1",
        idempotency_key="person-archive", occurred_at_ms=2,
    )
    with pytest.raises(ValueError, match="active person"):
        employees.create(
            tenant_id="tenant-1", business_id="business-1", employee_id="emp-1",
            person_id="person-1", organization_id="org-1", idempotency_key="emp-1", occurred_at_ms=3,
        )

    events2, organizations2, people2, employees2 = _stack()
    del events2
    _seed(organizations2, people2)
    organizations2.archive(
        tenant_id="tenant-1", business_id="business-1", organization_id="org-1",
        idempotency_key="org-archive", occurred_at_ms=2,
    )
    with pytest.raises(ValueError, match="active organization"):
        employees2.create(
            tenant_id="tenant-1", business_id="business-1", employee_id="emp-1",
            person_id="person-1", organization_id="org-1", idempotency_key="emp-1", occurred_at_ms=3,
        )


def test_employee_projection_is_tenant_business_scoped() -> None:
    events, organizations, people, employees = _stack()
    _seed(organizations, people, tenant_id="tenant-a", business_id="business-a")
    employees.create(
        tenant_id="tenant-a", business_id="business-a", employee_id="shared",
        person_id="person-1", organization_id="org-1", idempotency_key="emp-a", occurred_at_ms=2,
    )
    projector = EmployeeProjector(events)
    assert projector.get(tenant_id="tenant-a", business_id="business-a", employee_id="shared").employee_id == "shared"
    with pytest.raises(EmployeeNotFound):
        projector.get(tenant_id="tenant-a", business_id="business-b", employee_id="shared")


def test_employee_event_metadata_propagates_and_replay_rejects_change() -> None:
    events, organizations, people, employees = _stack()
    _seed(organizations, people)
    create_metadata = {"actor_id": "owner-1", "decision_id": "employee-create", "evidence_ids": ("e-employee",)}
    created = employees.create( tenant_id="tenant-1", business_id="business-1", employee_id="emp-meta", person_id="person-1", organization_id="org-1", idempotency_key="create-meta", occurred_at_ms=10, event_metadata=create_metadata, )
    assert employees.create( tenant_id="tenant-1", business_id="business-1", employee_id="emp-meta", person_id="person-1", organization_id="org-1", idempotency_key="create-meta", occurred_at_ms=999, event_metadata=create_metadata, ) == created
    employee_events = [e for e in events.events if str(dict(e.get("payload") or {}).get("fact_type") or "").startswith("employee.")]
    assert canonical_business_event_contract(employee_events[0])["actor_id"] == "owner-1"
    with pytest.raises(ValueError, match="event metadata"):
        employees.create( tenant_id="tenant-1", business_id="business-1", employee_id="emp-meta", person_id="person-1", organization_id="org-1", idempotency_key="create-meta", occurred_at_ms=10, event_metadata={**create_metadata, "actor_id": "owner-2"}, )
    archive_metadata = {"actor_id": "owner-1", "decision_id": "employee-archive"}
    archived = employees.archive( tenant_id="tenant-1", business_id="business-1", employee_id="emp-meta", idempotency_key="archive-meta", occurred_at_ms=20, event_metadata=archive_metadata, )
    assert employees.archive( tenant_id="tenant-1", business_id="business-1", employee_id="emp-meta", idempotency_key="archive-meta", occurred_at_ms=999, event_metadata=archive_metadata, ) == archived
    with pytest.raises(ValueError, match="event metadata"):
        employees.archive( tenant_id="tenant-1", business_id="business-1", employee_id="emp-meta", idempotency_key="archive-meta", occurred_at_ms=20, event_metadata={**archive_metadata, "actor_id": "owner-2"}, )

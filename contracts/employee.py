from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

CANON_EMPLOYEE_CONTRACT = True


class EmployeeStatus(StrEnum):
    ACTIVE = "active"
    ARCHIVED = "archived"


@dataclass(frozen=True, slots=True)
class Employee:
    """PII-minimal employment relationship between Person and Organization."""

    employee_id: str
    tenant_id: str
    business_id: str
    person_id: str
    organization_id: str
    status: EmployeeStatus = EmployeeStatus.ACTIVE
    created_at_ms: int = 0
    updated_at_ms: int = 0
    archived_at_ms: int | None = None

    def __post_init__(self) -> None:
        for field_name in ("employee_id", "tenant_id", "business_id", "person_id", "organization_id"):
            value = str(getattr(self, field_name) or "").strip()
            if not value or len(value) > 200 or any(ord(ch) < 32 for ch in value):
                raise ValueError(f"invalid {field_name}")
            object.__setattr__(self, field_name, value)
        object.__setattr__(self, "status", EmployeeStatus(self.status))
        created, updated = int(self.created_at_ms), int(self.updated_at_ms)
        if created < 0 or updated < created:
            raise ValueError("employee timestamps are invalid")
        object.__setattr__(self, "created_at_ms", created)
        object.__setattr__(self, "updated_at_ms", updated)
        if self.archived_at_ms is not None:
            archived = int(self.archived_at_ms)
            if archived < created:
                raise ValueError("archived_at_ms must be >= created_at_ms")
            object.__setattr__(self, "archived_at_ms", archived)
        if self.status is EmployeeStatus.ARCHIVED and self.archived_at_ms is None:
            raise ValueError("archived employee requires archived_at_ms")
        if self.status is EmployeeStatus.ACTIVE and self.archived_at_ms is not None:
            raise ValueError("active employee cannot have archived_at_ms")


class EmployeeNotFound(LookupError):
    pass


__all__ = ["CANON_EMPLOYEE_CONTRACT", "Employee", "EmployeeNotFound", "EmployeeStatus"]

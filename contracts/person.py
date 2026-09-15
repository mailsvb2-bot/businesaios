from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

CANON_PERSON_CONTRACT = True


class PersonStatus(StrEnum):
    ACTIVE = "active"
    ARCHIVED = "archived"


@dataclass(frozen=True, slots=True)
class Person:
    """PII-minimal canonical human identity.

    Contact identifiers and names are intentionally not persisted here; those
    remain in dedicated privacy-aware surfaces such as Customer + SecretVault.
    """

    person_id: str
    tenant_id: str
    business_id: str
    status: PersonStatus = PersonStatus.ACTIVE
    created_at_ms: int = 0
    updated_at_ms: int = 0
    archived_at_ms: int | None = None

    def __post_init__(self) -> None:
        for field_name in ("person_id", "tenant_id", "business_id"):
            value = str(getattr(self, field_name) or "").strip()
            if not value or len(value) > 200 or any(ord(ch) < 32 for ch in value):
                raise ValueError(f"invalid {field_name}")
            object.__setattr__(self, field_name, value)
        object.__setattr__(self, "status", PersonStatus(self.status))
        created, updated = int(self.created_at_ms), int(self.updated_at_ms)
        if created < 0 or updated < created:
            raise ValueError("person timestamps are invalid")
        object.__setattr__(self, "created_at_ms", created)
        object.__setattr__(self, "updated_at_ms", updated)
        if self.archived_at_ms is not None:
            archived = int(self.archived_at_ms)
            if archived < created:
                raise ValueError("archived_at_ms must be >= created_at_ms")
            object.__setattr__(self, "archived_at_ms", archived)
        if self.status is PersonStatus.ARCHIVED and self.archived_at_ms is None:
            raise ValueError("archived person requires archived_at_ms")
        if self.status is PersonStatus.ACTIVE and self.archived_at_ms is not None:
            raise ValueError("active person cannot have archived_at_ms")


class PersonNotFound(LookupError):
    pass


__all__ = ["CANON_PERSON_CONTRACT", "Person", "PersonNotFound", "PersonStatus"]

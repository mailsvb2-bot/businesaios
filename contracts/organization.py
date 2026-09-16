from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

CANON_ORGANIZATION_CONTRACT = True


class OrganizationStatus(StrEnum):
    ACTIVE = "active"
    ARCHIVED = "archived"


def _required(value: object, field_name: str, limit: int = 200) -> str:
    text = str(value or "").strip()
    if not text or len(text) > limit or any(ord(ch) < 32 for ch in text):
        raise ValueError(f"invalid {field_name}")
    return text


def _optional(value: object, field_name: str, limit: int = 300) -> str | None:
    if value is None:
        return None
    text = " ".join(str(value).replace("\x00", " ").split()).strip()
    if not text:
        return None
    if len(text) > limit or any(ord(ch) < 32 for ch in text):
        raise ValueError(f"invalid {field_name}")
    return text


@dataclass(frozen=True, slots=True)
class Organization:
    organization_id: str
    tenant_id: str
    business_id: str
    name: str | None = None
    organization_type: str | None = None
    status: OrganizationStatus = OrganizationStatus.ACTIVE
    created_at_ms: int = 0
    updated_at_ms: int = 0
    archived_at_ms: int | None = None

    def __post_init__(self) -> None:
        for field_name in ("organization_id", "tenant_id", "business_id"):
            object.__setattr__(self, field_name, _required(getattr(self, field_name), field_name))
        object.__setattr__(self, "name", _optional(self.name, "name"))
        object.__setattr__(self, "organization_type", _optional(self.organization_type, "organization_type", 100))
        object.__setattr__(self, "status", OrganizationStatus(self.status))
        created = int(self.created_at_ms)
        updated = int(self.updated_at_ms)
        if created < 0 or updated < created:
            raise ValueError("organization timestamps are invalid")
        object.__setattr__(self, "created_at_ms", created)
        object.__setattr__(self, "updated_at_ms", updated)
        if self.archived_at_ms is not None:
            archived = int(self.archived_at_ms)
            if archived < created:
                raise ValueError("archived_at_ms must be >= created_at_ms")
            object.__setattr__(self, "archived_at_ms", archived)
        if self.status is OrganizationStatus.ARCHIVED and self.archived_at_ms is None:
            raise ValueError("archived organization requires archived_at_ms")
        if self.status is OrganizationStatus.ACTIVE and self.archived_at_ms is not None:
            raise ValueError("active organization cannot have archived_at_ms")


class OrganizationNotFound(LookupError):
    pass


__all__ = [
    "CANON_ORGANIZATION_CONTRACT",
    "Organization",
    "OrganizationNotFound",
    "OrganizationStatus",
]

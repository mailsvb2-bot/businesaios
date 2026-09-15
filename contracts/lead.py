from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

CANON_LEAD_CONTRACT = True


class LeadLifecycleStatus(StrEnum):
    ACTIVE = "active"
    ARCHIVED = "archived"


def _required(value: object, field_name: str, limit: int = 200) -> str:
    text = str(value or "").strip()
    if not text or len(text) > limit or any(ord(ch) < 32 for ch in text):
        raise ValueError(f"invalid {field_name}")
    return text


def _optional(value: object, field_name: str, limit: int = 200) -> str | None:
    if value is None:
        return None
    text = " ".join(str(value).replace("\x00", " ").split()).strip()
    if not text:
        return None
    if len(text) > limit or any(ord(ch) < 32 for ch in text):
        raise ValueError(f"invalid {field_name}")
    return text


@dataclass(frozen=True, slots=True)
class Lead:
    """PII-minimal canonical business lead identity.

    Names, email addresses and phone numbers stay in CRM/PII-owned surfaces.
    """

    lead_id: str
    tenant_id: str
    business_id: str
    source: str | None = None
    status: str | None = None
    lifecycle_status: LeadLifecycleStatus = LeadLifecycleStatus.ACTIVE
    created_at_ms: int = 0
    updated_at_ms: int = 0
    archived_at_ms: int | None = None

    def __post_init__(self) -> None:
        for field_name in ("lead_id", "tenant_id", "business_id"):
            object.__setattr__(self, field_name, _required(getattr(self, field_name), field_name))
        object.__setattr__(self, "source", _optional(self.source, "source", 120))
        object.__setattr__(self, "status", _optional(self.status, "status", 120))
        object.__setattr__(self, "lifecycle_status", LeadLifecycleStatus(self.lifecycle_status))
        created, updated = int(self.created_at_ms), int(self.updated_at_ms)
        if created < 0 or updated < created:
            raise ValueError("lead timestamps are invalid")
        object.__setattr__(self, "created_at_ms", created)
        object.__setattr__(self, "updated_at_ms", updated)
        if self.archived_at_ms is not None:
            archived = int(self.archived_at_ms)
            if archived < created:
                raise ValueError("archived_at_ms must be >= created_at_ms")
            object.__setattr__(self, "archived_at_ms", archived)
        if self.lifecycle_status is LeadLifecycleStatus.ARCHIVED and self.archived_at_ms is None:
            raise ValueError("archived lead requires archived_at_ms")
        if self.lifecycle_status is LeadLifecycleStatus.ACTIVE and self.archived_at_ms is not None:
            raise ValueError("active lead cannot have archived_at_ms")


class LeadNotFound(LookupError):
    pass


__all__ = ["CANON_LEAD_CONTRACT", "Lead", "LeadLifecycleStatus", "LeadNotFound"]

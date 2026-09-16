from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

BUSINESS_RESOURCE_SCHEMA_VERSION = 1
CANON_BUSINESS_RESOURCE_CONTRACT = True


class ResourceLifecycleStatus(StrEnum):
    ACTIVE = "active"
    ARCHIVED = "archived"


def _required(value: object, field_name: str, limit: int = 200) -> str:
    text = str(value or "").strip()
    if not text or len(text) > limit or any(ord(ch) < 32 for ch in text):
        raise ValueError(f"invalid {field_name}")
    return text


def _optional(value: object, field_name: str, limit: int = 160) -> str | None:
    if value is None:
        return None
    text = " ".join(str(value).replace("\x00", " ").split()).strip()
    if not text:
        return None
    if len(text) > limit or any(ord(ch) < 32 for ch in text):
        raise ValueError(f"invalid {field_name}")
    return text


@dataclass(frozen=True, slots=True)
class BusinessResource:
    """PII-free canonical operational Resource identity.

    A business Resource is deliberately narrower than technical runtime resources:
    it owns business identity/lifecycle only. Capacity, scheduling and allocation
    policies remain separate domain concerns.
    """

    resource_id: str
    tenant_id: str
    business_id: str
    resource_kind: str
    state_key: str | None = None
    asset_id: str | None = None
    schema_version: int = BUSINESS_RESOURCE_SCHEMA_VERSION
    lifecycle_status: ResourceLifecycleStatus = ResourceLifecycleStatus.ACTIVE
    created_at_ms: int = 0
    updated_at_ms: int = 0
    archived_at_ms: int | None = None

    def __post_init__(self) -> None:
        for field_name in ("resource_id", "tenant_id", "business_id", "resource_kind"):
            object.__setattr__(self, field_name, _required(getattr(self, field_name), field_name))
        object.__setattr__(self, "state_key", _optional(self.state_key, "state_key"))
        object.__setattr__(self, "asset_id", _optional(self.asset_id, "asset_id", 200))
        if isinstance(self.schema_version, bool) or int(self.schema_version) != BUSINESS_RESOURCE_SCHEMA_VERSION:
            raise ValueError(f"unsupported business resource schema_version: {self.schema_version}")
        object.__setattr__(self, "schema_version", BUSINESS_RESOURCE_SCHEMA_VERSION)
        object.__setattr__(self, "lifecycle_status", ResourceLifecycleStatus(self.lifecycle_status))
        created, updated = int(self.created_at_ms), int(self.updated_at_ms)
        if created < 0 or updated < created:
            raise ValueError("business resource timestamps are invalid")
        object.__setattr__(self, "created_at_ms", created)
        object.__setattr__(self, "updated_at_ms", updated)
        if self.archived_at_ms is not None:
            archived = int(self.archived_at_ms)
            if archived < created:
                raise ValueError("archived_at_ms must be >= created_at_ms")
            object.__setattr__(self, "archived_at_ms", archived)
        if self.lifecycle_status is ResourceLifecycleStatus.ARCHIVED and self.archived_at_ms is None:
            raise ValueError("archived business resource requires archived_at_ms")
        if self.lifecycle_status is ResourceLifecycleStatus.ACTIVE and self.archived_at_ms is not None:
            raise ValueError("active business resource cannot have archived_at_ms")


class BusinessResourceNotFound(LookupError):
    pass


__all__ = [
    "BUSINESS_RESOURCE_SCHEMA_VERSION",
    "CANON_BUSINESS_RESOURCE_CONTRACT",
    "BusinessResource",
    "BusinessResourceNotFound",
    "ResourceLifecycleStatus",
]

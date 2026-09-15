from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

CANON_ASSET_CONTRACT = True
ASSET_SCHEMA_VERSION = 1


class AssetLifecycleStatus(StrEnum):
    ACTIVE = "active"
    ARCHIVED = "archived"


def _required(value: object, field_name: str, limit: int = 200) -> str:
    text = str(value or "").strip()
    if not text or len(text) > limit or any(ord(ch) < 32 for ch in text):
        raise ValueError(f"invalid {field_name}")
    return text


def _optional(value: object, field_name: str, limit: int = 120) -> str | None:
    if value is None:
        return None
    text = " ".join(str(value).replace("\x00", " ").split()).strip()
    if not text:
        return None
    if len(text) > limit or any(ord(ch) < 32 for ch in text):
        raise ValueError(f"invalid {field_name}")
    return text


@dataclass(frozen=True, slots=True)
class Asset:
    """PII-free canonical business asset identity and lifecycle."""

    asset_id: str
    tenant_id: str
    business_id: str
    asset_kind: str
    state_key: str | None = None
    book_value_minor: int | None = None
    currency: str | None = None
    schema_version: int = ASSET_SCHEMA_VERSION
    lifecycle_status: AssetLifecycleStatus = AssetLifecycleStatus.ACTIVE
    created_at_ms: int = 0
    updated_at_ms: int = 0
    archived_at_ms: int | None = None

    def __post_init__(self) -> None:
        for field_name in ("asset_id", "tenant_id", "business_id", "asset_kind"):
            object.__setattr__(self, field_name, _required(getattr(self, field_name), field_name))
        object.__setattr__(self, "state_key", _optional(self.state_key, "state_key"))
        if isinstance(self.schema_version, bool) or int(self.schema_version) != ASSET_SCHEMA_VERSION:
            raise ValueError(f"unsupported asset schema_version: {self.schema_version}")
        object.__setattr__(self, "schema_version", ASSET_SCHEMA_VERSION)
        value = self.book_value_minor
        if value is not None and (isinstance(value, bool) or not isinstance(value, int)):
            raise ValueError("book_value_minor must be an integer minor-unit value")
        if value is not None and value < 0:
            raise ValueError("book_value_minor cannot be negative")
        currency = _optional(self.currency, "currency", 16)
        if currency is not None:
            currency = currency.upper()
            if len(currency) != 3 or not currency.isalpha():
                raise ValueError("currency must be a 3-letter code")
        if value is not None and currency is None:
            raise ValueError("currency is required when book_value_minor is set")
        object.__setattr__(self, "book_value_minor", value)
        object.__setattr__(self, "currency", currency)
        object.__setattr__(self, "lifecycle_status", AssetLifecycleStatus(self.lifecycle_status))
        created, updated = int(self.created_at_ms), int(self.updated_at_ms)
        if created < 0 or updated < created:
            raise ValueError("asset timestamps are invalid")
        object.__setattr__(self, "created_at_ms", created)
        object.__setattr__(self, "updated_at_ms", updated)
        if self.archived_at_ms is not None:
            archived = int(self.archived_at_ms)
            if archived < created:
                raise ValueError("archived_at_ms must be >= created_at_ms")
            object.__setattr__(self, "archived_at_ms", archived)
        if self.lifecycle_status is AssetLifecycleStatus.ARCHIVED and self.archived_at_ms is None:
            raise ValueError("archived asset requires archived_at_ms")
        if self.lifecycle_status is AssetLifecycleStatus.ACTIVE and self.archived_at_ms is not None:
            raise ValueError("active asset cannot have archived_at_ms")


class AssetNotFound(LookupError):
    pass


__all__ = [
    "ASSET_SCHEMA_VERSION",
    "CANON_ASSET_CONTRACT",
    "Asset",
    "AssetLifecycleStatus",
    "AssetNotFound",
]

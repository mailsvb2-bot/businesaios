from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

CANON_OPPORTUNITY_CONTRACT = True


class OpportunityLifecycleStatus(StrEnum):
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
class Opportunity:
    """PII-free canonical business opportunity lifecycle identity."""

    opportunity_id: str
    tenant_id: str
    business_id: str
    source_kind: str | None = None
    stage_key: str | None = None
    expected_value_minor: int | None = None
    currency: str | None = None
    lifecycle_status: OpportunityLifecycleStatus = OpportunityLifecycleStatus.ACTIVE
    created_at_ms: int = 0
    updated_at_ms: int = 0
    archived_at_ms: int | None = None

    def __post_init__(self) -> None:
        for field_name in ("opportunity_id", "tenant_id", "business_id"):
            object.__setattr__(self, field_name, _required(getattr(self, field_name), field_name))
        object.__setattr__(self, "source_kind", _optional(self.source_kind, "source_kind"))
        object.__setattr__(self, "stage_key", _optional(self.stage_key, "stage_key"))
        value = self.expected_value_minor
        if value is not None and (isinstance(value, bool) or not isinstance(value, int)):
            raise ValueError("expected_value_minor must be an integer minor-unit value")
        if value is not None and value < 0:
            raise ValueError("expected_value_minor cannot be negative")
        currency = _optional(self.currency, "currency", 16)
        if currency is not None:
            currency = currency.upper()
            if len(currency) != 3 or not currency.isalpha():
                raise ValueError("currency must be a 3-letter code")
        if value is not None and currency is None:
            raise ValueError("currency is required when expected_value_minor is set")
        object.__setattr__(self, "expected_value_minor", value)
        object.__setattr__(self, "currency", currency)
        object.__setattr__(self, "lifecycle_status", OpportunityLifecycleStatus(self.lifecycle_status))
        created, updated = int(self.created_at_ms), int(self.updated_at_ms)
        if created < 0 or updated < created:
            raise ValueError("opportunity timestamps are invalid")
        object.__setattr__(self, "created_at_ms", created)
        object.__setattr__(self, "updated_at_ms", updated)
        if self.archived_at_ms is not None:
            archived = int(self.archived_at_ms)
            if archived < created:
                raise ValueError("archived_at_ms must be >= created_at_ms")
            object.__setattr__(self, "archived_at_ms", archived)
        if self.lifecycle_status is OpportunityLifecycleStatus.ARCHIVED and self.archived_at_ms is None:
            raise ValueError("archived opportunity requires archived_at_ms")
        if self.lifecycle_status is OpportunityLifecycleStatus.ACTIVE and self.archived_at_ms is not None:
            raise ValueError("active opportunity cannot have archived_at_ms")


class OpportunityNotFound(LookupError):
    pass


__all__ = ["CANON_OPPORTUNITY_CONTRACT", "Opportunity", "OpportunityLifecycleStatus", "OpportunityNotFound"]

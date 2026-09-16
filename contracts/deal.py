from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

CANON_DEAL_CONTRACT = True


class DealLifecycleStatus(StrEnum):
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
class Deal:
    """PII-free canonical commercial deal lifecycle identity."""

    deal_id: str
    tenant_id: str
    business_id: str
    pipeline_key: str | None = None
    stage_key: str | None = None
    amount_minor: int | None = None
    currency: str | None = None
    lifecycle_status: DealLifecycleStatus = DealLifecycleStatus.ACTIVE
    created_at_ms: int = 0
    updated_at_ms: int = 0
    archived_at_ms: int | None = None

    def __post_init__(self) -> None:
        for field_name in ("deal_id", "tenant_id", "business_id"):
            object.__setattr__(self, field_name, _required(getattr(self, field_name), field_name))
        object.__setattr__(self, "pipeline_key", _optional(self.pipeline_key, "pipeline_key"))
        object.__setattr__(self, "stage_key", _optional(self.stage_key, "stage_key"))
        if self.amount_minor is not None and (isinstance(self.amount_minor, bool) or not isinstance(self.amount_minor, int)):
            raise ValueError("amount_minor must be an integer minor-unit value")
        amount = self.amount_minor
        if amount is not None and amount < 0:
            raise ValueError("amount_minor cannot be negative")
        currency = _optional(self.currency, "currency", 16)
        if currency is not None:
            currency = currency.upper()
            if len(currency) != 3 or not currency.isalpha():
                raise ValueError("currency must be a 3-letter code")
        if amount is not None and currency is None:
            raise ValueError("currency is required when amount_minor is set")
        object.__setattr__(self, "amount_minor", amount)
        object.__setattr__(self, "currency", currency)
        object.__setattr__(self, "lifecycle_status", DealLifecycleStatus(self.lifecycle_status))
        created, updated = int(self.created_at_ms), int(self.updated_at_ms)
        if created < 0 or updated < created:
            raise ValueError("deal timestamps are invalid")
        object.__setattr__(self, "created_at_ms", created)
        object.__setattr__(self, "updated_at_ms", updated)
        if self.archived_at_ms is not None:
            archived = int(self.archived_at_ms)
            if archived < created:
                raise ValueError("archived_at_ms must be >= created_at_ms")
            object.__setattr__(self, "archived_at_ms", archived)
        if self.lifecycle_status is DealLifecycleStatus.ARCHIVED and self.archived_at_ms is None:
            raise ValueError("archived deal requires archived_at_ms")
        if self.lifecycle_status is DealLifecycleStatus.ACTIVE and self.archived_at_ms is not None:
            raise ValueError("active deal cannot have archived_at_ms")


class DealNotFound(LookupError):
    pass


__all__ = ["CANON_DEAL_CONTRACT", "Deal", "DealLifecycleStatus", "DealNotFound"]

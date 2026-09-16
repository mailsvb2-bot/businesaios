from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

CANON_CAMPAIGN_CONTRACT = True


class CampaignLifecycleStatus(StrEnum):
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
class Campaign:
    """PII-free canonical business campaign lifecycle identity."""

    campaign_id: str
    tenant_id: str
    business_id: str
    channel_key: str | None = None
    objective_key: str | None = None
    budget_minor: int | None = None
    currency: str | None = None
    lifecycle_status: CampaignLifecycleStatus = CampaignLifecycleStatus.ACTIVE
    created_at_ms: int = 0
    updated_at_ms: int = 0
    archived_at_ms: int | None = None

    def __post_init__(self) -> None:
        for field_name in ("campaign_id", "tenant_id", "business_id"):
            object.__setattr__(self, field_name, _required(getattr(self, field_name), field_name))
        object.__setattr__(self, "channel_key", _optional(self.channel_key, "channel_key"))
        object.__setattr__(self, "objective_key", _optional(self.objective_key, "objective_key"))
        if self.budget_minor is not None and (isinstance(self.budget_minor, bool) or not isinstance(self.budget_minor, int)):
            raise ValueError("budget_minor must be an integer minor-unit value")
        budget = self.budget_minor
        if budget is not None and budget < 0:
            raise ValueError("budget_minor cannot be negative")
        currency = _optional(self.currency, "currency", 16)
        if currency is not None:
            currency = currency.upper()
            if len(currency) != 3 or not currency.isalpha():
                raise ValueError("currency must be a 3-letter code")
        if budget is not None and currency is None:
            raise ValueError("currency is required when budget_minor is set")
        object.__setattr__(self, "budget_minor", budget)
        object.__setattr__(self, "currency", currency)
        object.__setattr__(self, "lifecycle_status", CampaignLifecycleStatus(self.lifecycle_status))
        created, updated = int(self.created_at_ms), int(self.updated_at_ms)
        if created < 0 or updated < created:
            raise ValueError("campaign timestamps are invalid")
        object.__setattr__(self, "created_at_ms", created)
        object.__setattr__(self, "updated_at_ms", updated)
        if self.archived_at_ms is not None:
            archived = int(self.archived_at_ms)
            if archived < created:
                raise ValueError("archived_at_ms must be >= created_at_ms")
            object.__setattr__(self, "archived_at_ms", archived)
        if self.lifecycle_status is CampaignLifecycleStatus.ARCHIVED and self.archived_at_ms is None:
            raise ValueError("archived campaign requires archived_at_ms")
        if self.lifecycle_status is CampaignLifecycleStatus.ACTIVE and self.archived_at_ms is not None:
            raise ValueError("active campaign cannot have archived_at_ms")


class CampaignNotFound(LookupError):
    pass


__all__ = ["CANON_CAMPAIGN_CONTRACT", "Campaign", "CampaignLifecycleStatus", "CampaignNotFound"]

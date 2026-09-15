from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

CANON_PARTNER_CONTRACT = True


class PartnerPartyKind(StrEnum):
    PERSON = "person"
    ORGANIZATION = "organization"


class PartnerStatus(StrEnum):
    ACTIVE = "active"
    ARCHIVED = "archived"


@dataclass(frozen=True, slots=True)
class Partner:
    """PII-minimal relationship to a canonical Person or Organization party."""

    partner_id: str
    tenant_id: str
    business_id: str
    party_kind: PartnerPartyKind
    party_id: str
    status: PartnerStatus = PartnerStatus.ACTIVE
    created_at_ms: int = 0
    updated_at_ms: int = 0
    archived_at_ms: int | None = None

    def __post_init__(self) -> None:
        for field_name in ("partner_id", "tenant_id", "business_id", "party_id"):
            value = str(getattr(self, field_name) or "").strip()
            if not value or len(value) > 200 or any(ord(ch) < 32 for ch in value):
                raise ValueError(f"invalid {field_name}")
            object.__setattr__(self, field_name, value)
        object.__setattr__(self, "party_kind", PartnerPartyKind(self.party_kind))
        object.__setattr__(self, "status", PartnerStatus(self.status))
        created, updated = int(self.created_at_ms), int(self.updated_at_ms)
        if created < 0 or updated < created:
            raise ValueError("partner timestamps are invalid")
        object.__setattr__(self, "created_at_ms", created)
        object.__setattr__(self, "updated_at_ms", updated)
        if self.archived_at_ms is not None:
            archived = int(self.archived_at_ms)
            if archived < created:
                raise ValueError("archived_at_ms must be >= created_at_ms")
            object.__setattr__(self, "archived_at_ms", archived)
        if self.status is PartnerStatus.ARCHIVED and self.archived_at_ms is None:
            raise ValueError("archived partner requires archived_at_ms")
        if self.status is PartnerStatus.ACTIVE and self.archived_at_ms is not None:
            raise ValueError("active partner cannot have archived_at_ms")


class PartnerNotFound(LookupError):
    pass


__all__ = ["CANON_PARTNER_CONTRACT", "Partner", "PartnerNotFound", "PartnerPartyKind", "PartnerStatus"]

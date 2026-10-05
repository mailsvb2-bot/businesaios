from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum
import re


def _required(value: object, field: str, maximum: int = 240) -> str:
    text = str(value or "").strip()
    if not text or len(text) > maximum:
        raise ValueError(f"{field} must be 1..{maximum} characters")
    return text


class IngressClassification(StrEnum):
    NEW = "new"
    DUPLICATE = "duplicate"
    STALE = "stale"


@dataclass(frozen=True, slots=True)
class ScopedInboundEvidence:
    tenant_id: str
    subject_id: str
    channel: str
    provider_event_id: str
    source_order_key: str
    text: str
    purpose: str = "sales"

    def __post_init__(self) -> None:
        for name in ("tenant_id", "subject_id", "channel", "provider_event_id", "source_order_key"):
            object.__setattr__(self, name, _required(getattr(self, name), name))
        normalized = " ".join(str(self.text or "").replace("\x00", " ").split())
        if not normalized:
            raise ValueError("text must not be empty")
        object.__setattr__(self, "text", normalized[:12000])
        object.__setattr__(self, "purpose", _required(self.purpose, "purpose", 80))

    @property
    def dedupe_key(self) -> tuple[str, str, str, str]:
        return (self.tenant_id, self.channel, self.subject_id, self.provider_event_id)


@dataclass(frozen=True, slots=True)
class IngressAssessment:
    classification: IngressClassification
    reason: str

    @property
    def usable_as_new_evidence(self) -> bool:
        return self.classification is IngressClassification.NEW


class DerivedConversationStage(StrEnum):
    DISCOVERED = "discovered"
    ENGAGED = "engaged"
    NEED_KNOWN = "need_known"
    QUALIFIED = "qualified"
    OFFER_PRESENTED = "offer_presented"
    CHECKOUT = "checkout"
    WON = "won"
    LOST = "lost"


@dataclass(frozen=True, slots=True)
class CommercialEvidence:
    inbound_seen: bool = False
    contact_seen: bool = False
    need_captured: bool = False
    qualified: bool = False
    offer_presented: bool = False
    checkout_requested: bool = False
    checkout_created: bool = False
    payment_confirmed: bool = False
    declined: bool = False


@dataclass(frozen=True, slots=True)
class VerifiedOfferEvidence:
    offer_id: str
    title: str
    active: bool
    amount_minor: int | None = None
    currency: str | None = None
    availability: str = "available"
    revision: int = 1

    def __post_init__(self) -> None:
        object.__setattr__(self, "offer_id", _required(self.offer_id, "offer_id"))
        object.__setattr__(self, "title", _required(self.title, "title", 500))
        if self.revision < 1:
            raise ValueError("offer revision must be >=1")
        if self.amount_minor is not None:
            if isinstance(self.amount_minor, bool) or int(self.amount_minor) < 0:
                raise ValueError("amount_minor must be non-negative")
            object.__setattr__(self, "amount_minor", int(self.amount_minor))
        if (self.amount_minor is None) != (self.currency is None):
            raise ValueError("price requires amount and currency together")
        if self.currency is not None:
            cur = str(self.currency).upper().strip()
            if not re.fullmatch(r"[A-Z]{3}", cur):
                raise ValueError("currency must be ISO-4217 alpha-3")
            object.__setattr__(self, "currency", cur)

    @property
    def sellable(self) -> bool:
        return self.active and self.availability == "available"

    @property
    def has_verified_price(self) -> bool:
        return self.amount_minor is not None and self.currency is not None


@dataclass(frozen=True, slots=True)
class OfferEvidenceAssessment:
    usable: bool
    reasons: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class FollowupConstraintContext:
    replied: bool = False
    booked: bool = False
    paid: bool = False
    opted_out: bool = False
    lead_closed: bool = False
    contact_allowed: bool = True
    channel_available: bool = True
    sent_in_sequence: int = 0
    max_sequence: int = 3
    fatigue: float = 0.0
    sent_24h: int = 0
    max_24h: int = 3
    sent_7d: int = 0
    max_7d: int = 8
    last_sent_at: datetime | None = None
    minimum_gap: timedelta = timedelta(0)
    channel_last_sent_at: datetime | None = None
    channel_minimum_gap: timedelta = timedelta(0)

    def __post_init__(self) -> None:
        if min(self.sent_in_sequence, self.max_sequence, self.sent_24h, self.max_24h, self.sent_7d, self.max_7d) < 0:
            raise ValueError("contact counters and caps must be non-negative")
        object.__setattr__(self, "fatigue", max(0.0, min(float(self.fatigue), 1.0)))
        if self.minimum_gap < timedelta(0) or self.channel_minimum_gap < timedelta(0):
            raise ValueError("minimum gaps must be non-negative")


@dataclass(frozen=True, slots=True)
class FollowupConstraintAssessment:
    blocked: bool
    reasons: tuple[str, ...]
    defer_until: datetime | None = None

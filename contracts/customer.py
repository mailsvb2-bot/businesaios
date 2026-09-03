from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

CANON_CUSTOMER_CONTRACT = True


class CustomerError(RuntimeError):
    pass


class CustomerNotFound(CustomerError):
    pass


class CustomerIdentityConflict(CustomerError):
    pass


class CustomerIdentityBusy(CustomerError):
    pass


class CustomerIdentityUnavailable(CustomerError):
    pass


class CustomerStatus(StrEnum):
    ACTIVE = "active"
    ARCHIVED = "archived"


class CustomerIdentityStatus(StrEnum):
    ACTIVE = "active"
    REVOKED = "revoked"


def _required(value: object, field_name: str, limit: int = 512) -> str:
    text = str(value or "").strip()
    if not text or len(text) > limit or any(ord(ch) < 32 for ch in text):
        raise ValueError(f"invalid {field_name}")
    return text


def normalize_customer_channel(value: object) -> str:
    channel = _required(value, "channel", 64).lower().replace("-", "_")
    if not re.fullmatch(r"[a-z0-9_]+", channel):
        raise ValueError("invalid channel")
    return channel


def normalize_customer_subject(channel: object, value: object) -> tuple[str, str]:
    normalized_channel = normalize_customer_channel(channel)
    subject = _required(value, "external_subject")
    if normalized_channel == "email":
        subject = subject.casefold()
    elif normalized_channel == "phone":
        subject = "".join(ch for ch in subject if ch.isdigit())
        if not 7 <= len(subject) <= 15:
            raise ValueError("phone identity must contain 7 to 15 digits")
    return normalized_channel, subject


def normalize_customer_optional_text(value: object, field_name: str, limit: int = 200) -> str | None:
    if value is None:
        return None
    text = " ".join(str(value).replace("\x00", " ").split()).strip()
    if not text:
        return None
    if len(text) > limit or any(ord(ch) < 32 for ch in text):
        raise ValueError(f"invalid {field_name}")
    return text


def _timestamp(value: object, field_name: str) -> int:
    try:
        result = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"invalid {field_name}") from exc
    if result < 0:
        raise ValueError(f"invalid {field_name}")
    return result


@dataclass(frozen=True, slots=True)
class Customer:
    customer_id: str
    tenant_id: str
    business_id: str
    display_name: str | None = None
    status: CustomerStatus = CustomerStatus.ACTIVE
    created_at_ms: int = 0
    updated_at_ms: int = 0
    archived_at_ms: int | None = None
    first_seen_at: object | None = None
    segment: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "customer_id", _required(self.customer_id, "customer_id", 200))
        object.__setattr__(self, "tenant_id", _required(self.tenant_id, "tenant_id", 200))
        object.__setattr__(self, "business_id", _required(self.business_id, "business_id", 200))
        object.__setattr__(self, "display_name", normalize_customer_optional_text(self.display_name, "display_name"))
        object.__setattr__(self, "status", CustomerStatus(self.status))
        object.__setattr__(self, "created_at_ms", _timestamp(self.created_at_ms, "created_at_ms"))
        object.__setattr__(self, "updated_at_ms", _timestamp(self.updated_at_ms, "updated_at_ms"))
        if self.updated_at_ms < self.created_at_ms:
            raise ValueError("updated_at_ms must be >= created_at_ms")
        if self.archived_at_ms is not None:
            object.__setattr__(self, "archived_at_ms", _timestamp(self.archived_at_ms, "archived_at_ms"))


@dataclass(frozen=True, slots=True)
class CustomerIdentity:
    identity_id: str
    tenant_id: str
    business_id: str
    customer_id: str
    channel: str
    external_subject: str
    username: str | None = None
    display_name: str | None = None
    status: CustomerIdentityStatus = CustomerIdentityStatus.ACTIVE
    created_at_ms: int = 0
    updated_at_ms: int = 0
    first_contact_at_ms: int | None = None
    last_contact_at_ms: int | None = None
    revoked_at_ms: int | None = None

    def __post_init__(self) -> None:
        for name in ("identity_id", "tenant_id", "business_id", "customer_id"):
            object.__setattr__(self, name, _required(getattr(self, name), name, 200))
        channel, subject = normalize_customer_subject(self.channel, self.external_subject)
        object.__setattr__(self, "channel", channel)
        object.__setattr__(self, "external_subject", subject)
        object.__setattr__(self, "username", normalize_customer_optional_text(self.username, "username"))
        object.__setattr__(self, "display_name", normalize_customer_optional_text(self.display_name, "display_name"))
        object.__setattr__(self, "status", CustomerIdentityStatus(self.status))
        object.__setattr__(self, "created_at_ms", _timestamp(self.created_at_ms, "created_at_ms"))
        object.__setattr__(self, "updated_at_ms", _timestamp(self.updated_at_ms, "updated_at_ms"))
        for name in ("first_contact_at_ms", "last_contact_at_ms", "revoked_at_ms"):
            value = getattr(self, name)
            if value is not None:
                object.__setattr__(self, name, _timestamp(value, name))


@dataclass(frozen=True, slots=True)
class CustomerRecord:
    customer: Customer
    identities: tuple[CustomerIdentity, ...] = field(default_factory=tuple)


@dataclass(frozen=True, slots=True)
class CustomerTimelineEntry:
    kind: str
    occurred_at_ms: int
    source_type: str
    source_id: str
    title: str
    detail: str | None = None
    amount_minor: int | None = None
    currency: str | None = None
    correlation_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for name in ("kind", "source_type", "source_id", "title"):
            object.__setattr__(self, name, _required(getattr(self, name), name, 300))
        object.__setattr__(self, "occurred_at_ms", _timestamp(self.occurred_at_ms, "occurred_at_ms"))
        object.__setattr__(self, "detail", normalize_customer_optional_text(self.detail, "detail", 1000))
        if self.amount_minor is not None and (isinstance(self.amount_minor, bool) or not isinstance(self.amount_minor, int)):
            raise TypeError("amount_minor must be an integer")
        if self.amount_minor is not None:
            currency = _required(self.currency, "currency", 3).upper()
            if len(currency) != 3 or not currency.isascii() or not currency.isalpha():
                raise ValueError("currency must be a three-letter code")
            object.__setattr__(self, "currency", currency)
        elif self.currency is not None:
            raise ValueError("currency without amount_minor is not allowed")
        object.__setattr__(self, "metadata", dict(self.metadata or {}))


@dataclass(frozen=True, slots=True)
class CustomerTimeline:
    tenant_id: str
    business_id: str
    customer_id: str
    entries: tuple[CustomerTimelineEntry, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        for name in ("tenant_id", "business_id", "customer_id"):
            object.__setattr__(self, name, _required(getattr(self, name), name, 200))


__all__ = [
    "CANON_CUSTOMER_CONTRACT", "Customer", "CustomerError", "CustomerIdentity",
    "CustomerIdentityBusy", "CustomerIdentityConflict", "CustomerIdentityStatus",
    "CustomerIdentityUnavailable",
    "CustomerNotFound", "CustomerRecord", "CustomerStatus", "CustomerTimeline",
    "CustomerTimelineEntry", "normalize_customer_channel", "normalize_customer_optional_text", "normalize_customer_subject",
]

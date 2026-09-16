from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

ORDER_SCHEMA_VERSION = 1
CANON_ORDER_CONTRACT = True


class OrderLifecycleStatus(StrEnum):
    ACTIVE = "active"
    FULFILLED = "fulfilled"
    CANCELLED = "cancelled"
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
class Order:
    """PII-free canonical business order identity and lifecycle."""

    order_id: str
    tenant_id: str
    business_id: str
    order_kind: str
    state_key: str | None = None
    schema_version: int = ORDER_SCHEMA_VERSION
    lifecycle_status: OrderLifecycleStatus = OrderLifecycleStatus.ACTIVE
    created_at_ms: int = 0
    updated_at_ms: int = 0
    terminal_at_ms: int | None = None

    def __post_init__(self) -> None:
        for field_name in ("order_id", "tenant_id", "business_id", "order_kind"):
            object.__setattr__(self, field_name, _required(getattr(self, field_name), field_name))
        object.__setattr__(self, "state_key", _optional(self.state_key, "state_key"))
        if isinstance(self.schema_version, bool) or int(self.schema_version) != ORDER_SCHEMA_VERSION:
            raise ValueError(f"unsupported order schema_version: {self.schema_version}")
        object.__setattr__(self, "schema_version", ORDER_SCHEMA_VERSION)
        object.__setattr__(self, "lifecycle_status", OrderLifecycleStatus(self.lifecycle_status))
        created, updated = int(self.created_at_ms), int(self.updated_at_ms)
        if created < 0 or updated < created:
            raise ValueError("order timestamps are invalid")
        object.__setattr__(self, "created_at_ms", created)
        object.__setattr__(self, "updated_at_ms", updated)
        terminal = self.terminal_at_ms
        if terminal is not None:
            terminal = int(terminal)
            if terminal < created:
                raise ValueError("terminal_at_ms must be >= created_at_ms")
            object.__setattr__(self, "terminal_at_ms", terminal)
        if self.lifecycle_status is OrderLifecycleStatus.ACTIVE and terminal is not None:
            raise ValueError("active order cannot have terminal_at_ms")
        if self.lifecycle_status is not OrderLifecycleStatus.ACTIVE and terminal is None:
            raise ValueError("terminal order requires terminal_at_ms")


class OrderNotFound(LookupError):
    pass


__all__ = [
    "CANON_ORDER_CONTRACT",
    "ORDER_SCHEMA_VERSION",
    "Order",
    "OrderLifecycleStatus",
    "OrderNotFound",
]

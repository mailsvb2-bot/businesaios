from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any

from core.tenancy.normalization import require_tenant_id

CANON_DISTRIBUTED_LOCK_CONTRACTS = True


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _normalize_ttl(ttl_seconds: int) -> int:
    ttl = int(ttl_seconds)
    if ttl <= 0:
        raise ValueError("ttl_seconds must be > 0")
    return ttl


def _normalize_resource(resource: str) -> str:
    value = str(resource or "").strip()
    if not value:
        raise ValueError("resource is required")
    return value


def _normalize_owner_id(owner_id: str) -> str:
    value = str(owner_id or "").strip()
    if not value:
        raise ValueError("owner_id is required")
    return value


@dataclass(frozen=True)
class LockLease:
    tenant_id: str
    resource: str
    owner_id: str
    fencing_token: int
    acquired_at: datetime = field(default_factory=utc_now)
    expires_at: datetime = field(default_factory=utc_now)

    def validate(self) -> None:
        require_tenant_id(self.tenant_id)
        _normalize_resource(self.resource)
        _normalize_owner_id(self.owner_id)
        if int(self.fencing_token) <= 0:
            raise ValueError("fencing_token must be > 0")
        if self.acquired_at.tzinfo is None or self.expires_at.tzinfo is None:
            raise ValueError("timestamps must be timezone-aware")
        if self.expires_at <= self.acquired_at:
            raise ValueError("expires_at must be > acquired_at")

    def is_live(self, *, now: datetime | None = None) -> bool:
        moment = now or utc_now()
        if moment.tzinfo is None:
            raise ValueError("now must be timezone-aware")
        return moment < self.expires_at


__all__ = ["CANON_DISTRIBUTED_LOCK_CONTRACTS", "LockLease", "utc_now", "_normalize_ttl", "_normalize_resource", "_normalize_owner_id"]

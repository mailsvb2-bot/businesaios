from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Protocol

from core.tenancy.normalization import require_tenant_id


CANON_TENANT_MIGRATION_LOCK_BACKEND = True


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def ensure_aware(value: datetime) -> datetime:
    if not isinstance(value, datetime):
        raise TypeError("datetime is required")
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("datetime must be timezone-aware")
    return value.astimezone(timezone.utc)


@dataclass(frozen=True)
class TenantMigrationLockRecord:
    tenant_id: str
    operation_id: str
    owner_id: str
    fencing_token: int
    acquired_at: datetime
    expires_at: datetime

    def validate(self) -> None:
        require_tenant_id(self.tenant_id)
        if not str(self.operation_id or "").strip():
            raise ValueError("operation_id is required")
        if not str(self.owner_id or "").strip():
            raise ValueError("owner_id is required")
        if int(self.fencing_token) <= 0:
            raise ValueError("fencing_token must be > 0")
        acquired_at = ensure_aware(self.acquired_at)
        expires_at = ensure_aware(self.expires_at)
        if expires_at <= acquired_at:
            raise ValueError("expires_at must be > acquired_at")


class TenantMigrationLockBackend(Protocol):
    def acquire(self, *, tenant_id: str, operation_id: str, owner_id: str, ttl_seconds: int, now: datetime | None = None) -> TenantMigrationLockRecord | None: ...
    def renew(self, *, tenant_id: str, operation_id: str, owner_id: str, ttl_seconds: int, now: datetime | None = None) -> TenantMigrationLockRecord: ...
    def release(self, *, tenant_id: str, operation_id: str, owner_id: str) -> bool: ...
    def get(self, *, tenant_id: str) -> TenantMigrationLockRecord | None: ...


__all__ = ["CANON_TENANT_MIGRATION_LOCK_BACKEND", "TenantMigrationLockBackend", "TenantMigrationLockRecord", "ensure_aware", "utc_now"]

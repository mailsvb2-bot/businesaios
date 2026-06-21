from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Protocol
import re

from core.tenancy.normalization import require_tenant_id
from reliability.distributed_lock_contracts import LockLease

CANON_DISTRIBUTED_LOCK_BACKEND = True
_SAFE_SQL_IDENTIFIER_RE = re.compile(r'^[A-Za-z_][A-Za-z0-9_]*$')

def utc_now() -> datetime:
    return datetime.now(timezone.utc)

def ensure_aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        raise ValueError('datetime must be timezone-aware')
    return value.astimezone(timezone.utc)

def normalize_resource(value: Any) -> str:
    resource = str(value or '').strip()
    if not resource:
        raise ValueError('resource is required')
    return resource

def normalize_owner_id(value: Any) -> str:
    owner_id = str(value or '').strip()
    if not owner_id:
        raise ValueError('owner_id is required')
    return owner_id

def normalize_ttl_seconds(value: int) -> int:
    ttl = int(value)
    if ttl <= 0:
        raise ValueError('ttl_seconds must be > 0')
    return ttl

def normalize_lock_inputs(*, tenant_id: Any, resource: Any, owner_id: Any, ttl_seconds: int, now: datetime | None = None) -> tuple[str, str, str, int, datetime]:
    return (
        require_tenant_id(tenant_id),
        normalize_resource(resource),
        normalize_owner_id(owner_id),
        normalize_ttl_seconds(ttl_seconds),
        ensure_aware(now or utc_now()),
    )

def build_expires_at(*, now: datetime, ttl_seconds: int) -> datetime:
    return ensure_aware(now) + timedelta(seconds=normalize_ttl_seconds(ttl_seconds))

def epoch_ms_to_datetime(value: int | str) -> datetime:
    return datetime.fromtimestamp(int(value) / 1000.0, tz=timezone.utc)

def datetime_to_epoch_ms(value: datetime) -> int:
    return int(ensure_aware(value).timestamp() * 1000)

def safe_sql_identifier(value: str) -> str:
    name = str(value or '').strip()
    if not name:
        raise ValueError('sql identifier is required')
    if not _SAFE_SQL_IDENTIFIER_RE.fullmatch(name):
        raise ValueError(f'unsafe sql identifier: {name!r}')
    return name

@dataclass(frozen=True)
class LockBackendRecord:
    tenant_id: str
    resource: str
    owner_id: str
    fencing_token: int
    acquired_at: datetime
    expires_at: datetime
    def validate(self) -> None:
        require_tenant_id(self.tenant_id)
        normalize_resource(self.resource)
        normalize_owner_id(self.owner_id)
        if int(self.fencing_token) <= 0:
            raise ValueError('fencing_token must be > 0')
        acquired_at = ensure_aware(self.acquired_at)
        expires_at = ensure_aware(self.expires_at)
        if expires_at <= acquired_at:
            raise ValueError('expires_at must be > acquired_at')
    def to_lease(self) -> LockLease:
        self.validate()
        lease = LockLease(
            tenant_id=self.tenant_id,
            resource=self.resource,
            owner_id=self.owner_id,
            fencing_token=int(self.fencing_token),
            acquired_at=ensure_aware(self.acquired_at),
            expires_at=ensure_aware(self.expires_at),
        )
        lease.validate()
        return lease
    @classmethod
    def from_lease(cls, lease: LockLease) -> 'LockBackendRecord':
        lease.validate()
        record = cls(
            tenant_id=lease.tenant_id,
            resource=lease.resource,
            owner_id=lease.owner_id,
            fencing_token=int(lease.fencing_token),
            acquired_at=ensure_aware(lease.acquired_at),
            expires_at=ensure_aware(lease.expires_at),
        )
        record.validate()
        return record

class DistributedLockBackend(Protocol):
    def ping(self) -> bool: ...
    def acquire(self, *, tenant_id: str, resource: str, owner_id: str, ttl_seconds: int = 30, now: datetime | None = None) -> LockLease | None: ...
    def renew(self, *, lease: LockLease, ttl_seconds: int = 30, now: datetime | None = None) -> LockLease: ...
    def release(self, *, lease: LockLease) -> None: ...
    def get(self, *, tenant_id: str, resource: str) -> LockLease | None: ...

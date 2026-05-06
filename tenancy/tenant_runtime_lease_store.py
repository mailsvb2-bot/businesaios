from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from threading import RLock
from typing import Mapping, Protocol

from core.tenancy.normalization import require_tenant_id
from tenancy.tenant_runtime_lease_fencing import TenantRuntimeLeaseFencingToken


CANON_TENANT_RUNTIME_LEASE_STORE = True


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def ensure_aware(value: datetime) -> datetime:
    if not isinstance(value, datetime):
        raise TypeError('datetime is required')
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError('datetime must be timezone-aware')
    return value.astimezone(timezone.utc)


def normalize_positive_int(value: int, *, field_name: str) -> int:
    number = int(value)
    if number <= 0:
        raise ValueError(f'{field_name} must be > 0')
    return number


def normalize_text(value: object, *, field_name: str) -> str:
    text = str(value or '').strip()
    if not text:
        raise ValueError(f'{field_name} is required')
    return text


@dataclass(frozen=True)
class TenantRuntimeLeaseRecord:
    tenant_id: str
    run_id: str
    owner_id: str
    slot_id: str
    fencing_token: int
    acquired_at: datetime
    heartbeat_at: datetime
    expires_at: datetime
    labels: Mapping[str, str] = field(default_factory=dict)

    def validate(self) -> None:
        require_tenant_id(self.tenant_id)
        normalize_text(self.run_id, field_name='run_id')
        normalize_text(self.owner_id, field_name='owner_id')
        normalize_text(self.slot_id, field_name='slot_id')
        if int(self.fencing_token) <= 0:
            raise ValueError('fencing_token must be > 0')
        acquired_at = ensure_aware(self.acquired_at)
        heartbeat_at = ensure_aware(self.heartbeat_at)
        expires_at = ensure_aware(self.expires_at)
        if heartbeat_at < acquired_at:
            raise ValueError('heartbeat_at must be >= acquired_at')
        if expires_at <= heartbeat_at:
            raise ValueError('expires_at must be > heartbeat_at')
        for key, value in dict(self.labels).items():
            normalize_text(key, field_name='label key')
            normalize_text(value, field_name='label value')

    @property
    def fencing(self) -> TenantRuntimeLeaseFencingToken:
        return TenantRuntimeLeaseFencingToken.parse(self.fencing_token)

    @property
    def expired(self) -> bool:
        return self.expires_at <= utc_now()


@dataclass(frozen=True)
class TenantRuntimeLeaseAcquireResult:
    allowed: bool
    reason: str
    tenant_id: str
    run_id: str
    active_runs: int
    limit: int
    lease: TenantRuntimeLeaseRecord | None = None


class TenantRuntimeLeaseStore(Protocol):
    def acquire(
        self,
        *,
        tenant_id: str,
        run_id: str,
        owner_id: str,
        limit: int,
        ttl_seconds: int,
        labels: Mapping[str, str] | None = None,
        now: datetime | None = None,
    ) -> TenantRuntimeLeaseAcquireResult: ...

    def renew(
        self,
        *,
        tenant_id: str,
        run_id: str,
        owner_id: str,
        ttl_seconds: int,
        now: datetime | None = None,
    ) -> TenantRuntimeLeaseRecord: ...

    def release(self, *, tenant_id: str, run_id: str, owner_id: str) -> bool: ...
    def get(self, *, tenant_id: str, run_id: str) -> TenantRuntimeLeaseRecord | None: ...
    def list_active(self, *, tenant_id: str, now: datetime | None = None) -> tuple[TenantRuntimeLeaseRecord, ...]: ...
    def reap_expired(self, *, now: datetime | None = None) -> tuple[TenantRuntimeLeaseRecord, ...]: ...


class InMemoryTenantRuntimeLeaseStore:
    def __init__(self) -> None:
        self._records: dict[tuple[str, str], TenantRuntimeLeaseRecord] = {}
        self._tokens_by_tenant: dict[str, int] = {}
        self._lock = RLock()

    def acquire(
        self,
        *,
        tenant_id: str,
        run_id: str,
        owner_id: str,
        limit: int,
        ttl_seconds: int,
        labels: Mapping[str, str] | None = None,
        now: datetime | None = None,
    ) -> TenantRuntimeLeaseAcquireResult:
        tid = require_tenant_id(tenant_id)
        rid = normalize_text(run_id, field_name='run_id')
        oid = normalize_text(owner_id, field_name='owner_id')
        max_active = max(0, int(limit))
        ttl = normalize_positive_int(ttl_seconds, field_name='ttl_seconds')
        moment = ensure_aware(now or utc_now())
        normalized_labels = {normalize_text(k, field_name='label key'): normalize_text(v, field_name='label value') for k, v in dict(labels or {}).items()}
        with self._lock:
            self._reap_expired_locked(now=moment)
            current = self._records.get((tid, rid))
            active_runs = self._active_count_locked(tenant_id=tid)
            if current is not None:
                if current.owner_id != oid:
                    return TenantRuntimeLeaseAcquireResult(False, 'lease_owned_by_another_owner', tid, rid, active_runs, max_active, current)
                if dict(current.labels) != normalized_labels:
                    return TenantRuntimeLeaseAcquireResult(False, 'lease_labels_mismatch', tid, rid, active_runs, max_active, current)
                renewed = self._renew_locked(current=current, ttl_seconds=ttl, now=moment)
                return TenantRuntimeLeaseAcquireResult(True, 'already_acquired', tid, rid, active_runs, max_active, renewed)
            if max_active <= 0:
                return TenantRuntimeLeaseAcquireResult(False, 'tenant_runtime_disabled', tid, rid, active_runs, max_active, None)
            if active_runs >= max_active:
                return TenantRuntimeLeaseAcquireResult(False, 'tenant_runtime_capacity_exceeded', tid, rid, active_runs, max_active, None)
            token = self._next_token_locked(tenant_id=tid)
            lease = TenantRuntimeLeaseRecord(
                tenant_id=tid,
                run_id=rid,
                owner_id=oid,
                slot_id=f'tenant/{tid}/runtime/{rid}',
                fencing_token=token,
                acquired_at=moment,
                heartbeat_at=moment,
                expires_at=moment + timedelta(seconds=ttl),
                labels=normalized_labels,
            )
            lease.validate()
            self._records[(tid, rid)] = lease
            return TenantRuntimeLeaseAcquireResult(True, 'acquired', tid, rid, self._active_count_locked(tenant_id=tid), max_active, lease)

    def renew(
        self,
        *,
        tenant_id: str,
        run_id: str,
        owner_id: str,
        ttl_seconds: int,
        now: datetime | None = None,
    ) -> TenantRuntimeLeaseRecord:
        tid = require_tenant_id(tenant_id)
        rid = normalize_text(run_id, field_name='run_id')
        oid = normalize_text(owner_id, field_name='owner_id')
        ttl = normalize_positive_int(ttl_seconds, field_name='ttl_seconds')
        moment = ensure_aware(now or utc_now())
        with self._lock:
            self._reap_expired_locked(now=moment)
            current = self._records.get((tid, rid))
            if current is None:
                raise KeyError(f'missing runtime lease: tenant={tid} run_id={rid}')
            if current.owner_id != oid:
                raise PermissionError(f'runtime lease owner mismatch: tenant={tid} run_id={rid}')
            return self._renew_locked(current=current, ttl_seconds=ttl, now=moment)

    def release(self, *, tenant_id: str, run_id: str, owner_id: str) -> bool:
        tid = require_tenant_id(tenant_id)
        rid = normalize_text(run_id, field_name='run_id')
        oid = normalize_text(owner_id, field_name='owner_id')
        with self._lock:
            current = self._records.get((tid, rid))
            if current is None:
                return False
            if current.owner_id != oid:
                raise PermissionError(f'runtime lease owner mismatch: tenant={tid} run_id={rid}')
            self._records.pop((tid, rid), None)
            return True

    def get(self, *, tenant_id: str, run_id: str) -> TenantRuntimeLeaseRecord | None:
        tid = require_tenant_id(tenant_id)
        rid = normalize_text(run_id, field_name='run_id')
        with self._lock:
            record = self._records.get((tid, rid))
            if record is None:
                return None
            if record.expired:
                self._records.pop((tid, rid), None)
                return None
            return record

    def list_active(self, *, tenant_id: str, now: datetime | None = None) -> tuple[TenantRuntimeLeaseRecord, ...]:
        tid = require_tenant_id(tenant_id)
        moment = ensure_aware(now or utc_now())
        with self._lock:
            self._reap_expired_locked(now=moment)
            items = [item for item in self._records.values() if item.tenant_id == tid]
            return tuple(sorted(items, key=lambda item: (item.acquired_at, item.run_id)))

    def reap_expired(self, *, now: datetime | None = None) -> tuple[TenantRuntimeLeaseRecord, ...]:
        moment = ensure_aware(now or utc_now())
        with self._lock:
            return self._reap_expired_locked(now=moment)

    def _renew_locked(self, *, current: TenantRuntimeLeaseRecord, ttl_seconds: int, now: datetime) -> TenantRuntimeLeaseRecord:
        renewed = TenantRuntimeLeaseRecord(
            tenant_id=current.tenant_id,
            run_id=current.run_id,
            owner_id=current.owner_id,
            slot_id=current.slot_id,
            fencing_token=current.fencing_token,
            acquired_at=current.acquired_at,
            heartbeat_at=now,
            expires_at=now + timedelta(seconds=ttl_seconds),
            labels=current.labels,
        )
        renewed.validate()
        self._records[(renewed.tenant_id, renewed.run_id)] = renewed
        return renewed

    def _reap_expired_locked(self, *, now: datetime) -> tuple[TenantRuntimeLeaseRecord, ...]:
        expired: list[TenantRuntimeLeaseRecord] = []
        for key, record in list(self._records.items()):
            if ensure_aware(record.expires_at) <= now:
                expired.append(record)
                self._records.pop(key, None)
        return tuple(sorted(expired, key=lambda item: (item.tenant_id, item.run_id)))

    def _active_count_locked(self, *, tenant_id: str) -> int:
        return sum(1 for item in self._records.values() if item.tenant_id == tenant_id)

    def _next_token_locked(self, *, tenant_id: str) -> int:
        token = int(self._tokens_by_tenant.get(tenant_id, 0)) + 1
        self._tokens_by_tenant[tenant_id] = token
        return token


__all__ = [
    'CANON_TENANT_RUNTIME_LEASE_STORE',
    'InMemoryTenantRuntimeLeaseStore',
    'TenantRuntimeLeaseAcquireResult',
    'TenantRuntimeLeaseRecord',
    'TenantRuntimeLeaseStore',
    'ensure_aware',
    'normalize_positive_int',
    'normalize_text',
    'utc_now',
]

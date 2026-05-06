from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime
from threading import RLock
from typing import Iterator, Mapping

from core.tenancy.normalization import require_tenant_id
from tenancy.tenant_contract import TenantPolicyStoreContract, utc_now


CANON_TENANT_RUNTIME_ISOLATION = True


@dataclass(frozen=True)
class TenantRuntimeIsolationLease:
    tenant_id: str
    run_id: str
    slot_id: str
    acquired_at: datetime
    owner_id: str | None = None
    labels: Mapping[str, str] = field(default_factory=dict)

    def validate(self) -> None:
        require_tenant_id(self.tenant_id)
        if not str(self.run_id or '').strip():
            raise ValueError('run_id is required')
        if not str(self.slot_id or '').strip():
            raise ValueError('slot_id is required')
        if self.owner_id is not None and not str(self.owner_id).strip():
            raise ValueError('owner_id must not be blank when provided')
        if not isinstance(self.acquired_at, datetime):
            raise TypeError('acquired_at must be a datetime')
        if self.acquired_at.tzinfo is None or self.acquired_at.utcoffset() is None:
            raise ValueError('acquired_at must be timezone-aware')
        for key, value in dict(self.labels).items():
            if not str(key or '').strip():
                raise ValueError('label key must be non-empty')
            if not str(value or '').strip():
                raise ValueError('label value must be non-empty')


@dataclass(frozen=True)
class TenantRuntimeIsolationVerdict:
    allowed: bool
    reason: str
    tenant_id: str
    run_id: str
    active_runs: int
    limit: int
    lease: TenantRuntimeIsolationLease | None = None

    @property
    def denied(self) -> bool:
        return not self.allowed


@dataclass(frozen=True)
class TenantRuntimeIsolationSnapshot:
    tenant_id: str
    active_runs: int
    limit: int
    leases: tuple[TenantRuntimeIsolationLease, ...] = ()

    def validate(self) -> None:
        require_tenant_id(self.tenant_id)
        if self.active_runs < 0:
            raise ValueError('active_runs must be >= 0')
        if self.limit < 0:
            raise ValueError('limit must be >= 0')
        for lease in self.leases:
            lease.validate()
            if require_tenant_id(lease.tenant_id) != require_tenant_id(self.tenant_id):
                raise ValueError('cross-tenant lease in snapshot is forbidden')


class TenantRuntimeIsolation:
    def __init__(self, *, policy_store: TenantPolicyStoreContract) -> None:
        self._policy_store = policy_store
        self._leases_by_tenant: dict[str, dict[str, TenantRuntimeIsolationLease]] = {}
        self._lease_depths: dict[tuple[str, str], int] = {}
        self._lock = RLock()

    def inspect(self, *, tenant_id: str) -> TenantRuntimeIsolationSnapshot:
        tid = require_tenant_id(tenant_id)
        with self._lock:
            tenant_leases = self._leases_by_tenant.get(tid, {})
            limit = self._limit_for(tid)
            leases = tuple(sorted(tenant_leases.values(), key=lambda item: (item.acquired_at, item.run_id, item.slot_id)))
            snapshot = TenantRuntimeIsolationSnapshot(tenant_id=tid, active_runs=len(leases), limit=limit, leases=leases)
            snapshot.validate()
            return snapshot

    def acquire(self, *, tenant_id: str, run_id: str, owner_id: str | None = None, labels: Mapping[str, str] | None = None, now: datetime | None = None) -> TenantRuntimeIsolationVerdict:
        tid = require_tenant_id(tenant_id)
        normalized_run_id = self._require_text(run_id, field_name='run_id')
        normalized_owner = self._normalize_optional_text(owner_id, field_name='owner_id')
        normalized_labels = self._normalize_labels(labels or {})
        moment = utc_now() if now is None else self._normalize_datetime(now, field_name='now')
        with self._lock:
            limit = self._limit_for(tid)
            tenant_leases = self._leases_by_tenant.setdefault(tid, {})
            existing = tenant_leases.get(normalized_run_id)
            if existing is not None:
                self._assert_reacquire_compatible(existing=existing, owner_id=normalized_owner, labels=normalized_labels)
                depth_key = (tid, normalized_run_id)
                self._lease_depths[depth_key] = int(self._lease_depths.get(depth_key, 1)) + 1
                return TenantRuntimeIsolationVerdict(True, 'already_acquired', tid, normalized_run_id, len(tenant_leases), limit, existing)
            if limit <= 0:
                return TenantRuntimeIsolationVerdict(False, 'tenant_runtime_disabled', tid, normalized_run_id, len(tenant_leases), limit, None)
            if len(tenant_leases) >= limit:
                return TenantRuntimeIsolationVerdict(False, 'tenant_runtime_concurrency_exceeded', tid, normalized_run_id, len(tenant_leases), limit, None)
            lease = TenantRuntimeIsolationLease(
                tenant_id=tid,
                run_id=normalized_run_id,
                slot_id=self._slot_id_for(tenant_id=tid, run_id=normalized_run_id),
                acquired_at=moment,
                owner_id=normalized_owner,
                labels=normalized_labels,
            )
            lease.validate()
            tenant_leases[normalized_run_id] = lease
            self._lease_depths[(tid, normalized_run_id)] = 1
            return TenantRuntimeIsolationVerdict(True, 'acquired', tid, normalized_run_id, len(tenant_leases), limit, lease)

    def release(self, *, tenant_id: str, run_id: str, owner_id: str | None = None) -> bool:
        tid = require_tenant_id(tenant_id)
        normalized_run_id = self._require_text(run_id, field_name='run_id')
        normalized_owner = self._normalize_optional_text(owner_id, field_name='owner_id')
        with self._lock:
            tenant_leases = self._leases_by_tenant.get(tid)
            if not tenant_leases:
                return False
            current = tenant_leases.get(normalized_run_id)
            if current is None:
                return False
            if current.owner_id is not None and normalized_owner != current.owner_id:
                raise PermissionError(f'tenant runtime lease owner mismatch for tenant={tid} run_id={normalized_run_id}')
            depth_key = (tid, normalized_run_id)
            depth = int(self._lease_depths.get(depth_key, 1))
            if depth > 1:
                self._lease_depths[depth_key] = depth - 1
                return True
            self._lease_depths.pop(depth_key, None)
            tenant_leases.pop(normalized_run_id, None)
            if not tenant_leases:
                self._leases_by_tenant.pop(tid, None)
            return True

    def require_lease(self, *, tenant_id: str, run_id: str) -> TenantRuntimeIsolationLease:
        tid = require_tenant_id(tenant_id)
        normalized_run_id = self._require_text(run_id, field_name='run_id')
        with self._lock:
            lease = self._leases_by_tenant.get(tid, {}).get(normalized_run_id)
            if lease is None:
                raise KeyError(f'missing tenant runtime isolation lease: tenant={tid} run_id={normalized_run_id}')
            return lease

    def assert_isolated(self, *, tenant_id: str, run_id: str) -> None:
        self.require_lease(tenant_id=tenant_id, run_id=run_id)

    @contextmanager
    def bind_run(self, *, tenant_id: str, run_id: str, owner_id: str | None = None, labels: Mapping[str, str] | None = None, now: datetime | None = None) -> Iterator[TenantRuntimeIsolationLease]:
        verdict = self.acquire(tenant_id=tenant_id, run_id=run_id, owner_id=owner_id, labels=labels, now=now)
        if not verdict.allowed or verdict.lease is None:
            raise RuntimeError(f'tenant runtime isolation denied: tenant={verdict.tenant_id} run_id={verdict.run_id} reason={verdict.reason}')
        try:
            yield verdict.lease
        finally:
            self.release(tenant_id=tenant_id, run_id=run_id, owner_id=owner_id)

    def _limit_for(self, tenant_id: str) -> int:
        bundle = self._policy_store.require(tenant_id)
        runtime_limits = getattr(bundle, 'runtime_limits', None)
        if runtime_limits is None:
            raise AttributeError('policy bundle must expose runtime_limits')
        raw = getattr(runtime_limits, 'max_concurrent_runs', None)
        if raw is None:
            raise AttributeError('runtime_limits must expose max_concurrent_runs')
        return max(0, int(raw))

    @staticmethod
    def _slot_id_for(*, tenant_id: str, run_id: str) -> str:
        return f"tenant/{require_tenant_id(tenant_id)}/runtime/{TenantRuntimeIsolation._clean_segment(run_id)}"

    @staticmethod
    def _assert_reacquire_compatible(*, existing: TenantRuntimeIsolationLease, owner_id: str | None, labels: Mapping[str, str]) -> None:
        if existing.owner_id is not None and owner_id != existing.owner_id:
            raise PermissionError(
                f'runtime lease already owned by another owner: tenant={existing.tenant_id} run_id={existing.run_id}'
            )
        if dict(existing.labels) != dict(labels):
            raise ValueError(
                f'runtime lease re-acquire labels mismatch: tenant={existing.tenant_id} run_id={existing.run_id}'
            )

    @staticmethod
    def _require_text(value: str, *, field_name: str) -> str:
        text = str(value or '').strip()
        if not text:
            raise ValueError(f'{field_name} is required')
        return text

    @staticmethod
    def _normalize_optional_text(value: str | None, *, field_name: str) -> str | None:
        if value is None:
            return None
        text = str(value).strip()
        if not text:
            raise ValueError(f'{field_name} must not be blank when provided')
        return text

    @staticmethod
    def _normalize_labels(labels: Mapping[str, str]) -> dict[str, str]:
        normalized: dict[str, str] = {}
        for key, value in dict(labels).items():
            k = str(key or '').strip()
            v = str(value or '').strip()
            if not k:
                raise ValueError('label key must be non-empty')
            if not v:
                raise ValueError('label value must be non-empty')
            normalized[k] = v
        return normalized

    @staticmethod
    def _normalize_datetime(value: datetime, *, field_name: str) -> datetime:
        if not isinstance(value, datetime):
            raise TypeError(f'{field_name} must be a datetime')
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError(f'{field_name} must be timezone-aware')
        return value

    @staticmethod
    def _clean_segment(value: str) -> str:
        text = str(value or '').strip()
        if not text:
            raise ValueError('segment is required')
        for forbidden in ('/', '\\', ':', '\n', '\r', '\t'):
            if forbidden in text:
                raise ValueError(f'segment contains forbidden character: {forbidden!r}')
        return text


__all__ = [
    'CANON_TENANT_RUNTIME_ISOLATION',
    'TenantRuntimeIsolation',
    'TenantRuntimeIsolationLease',
    'TenantRuntimeIsolationSnapshot',
    'TenantRuntimeIsolationVerdict',
]

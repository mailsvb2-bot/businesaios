from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Protocol
from uuid import uuid4

from billing.commercial_cycle_contract import utc_now
from core.tenancy.normalization import require_tenant_id
from runtime.platform.billing_scheduler_lease_store import (
    CANON_PLATFORM_BILLING_SCHEDULER_LEASE_STORE,
    LEASE_SCHEMA_VERSION,
    PlatformSqliteBillingJobLeaseStore,
)

CANON_BILLING_JOB_LEASES = True


@dataclass(frozen=True)
class BillingJobLease:
    tenant_id: str
    job_name: str
    run_key: str
    worker_id: str
    fencing_token: str = field(default_factory=lambda: uuid4().hex)
    acquired_at: datetime = field(default_factory=utc_now)
    expires_at: datetime | None = None
    metadata: dict[str, object] = field(default_factory=dict)

    def validate(self) -> None:
        require_tenant_id(self.tenant_id)
        if not str(self.job_name or '').strip():
            raise ValueError('job_name is required')
        if not str(self.run_key or '').strip():
            raise ValueError('run_key is required')
        if not str(self.worker_id or '').strip():
            raise ValueError('worker_id is required')
        if not str(self.fencing_token or '').strip():
            raise ValueError('fencing_token is required')
        if self.acquired_at.tzinfo is None:
            raise ValueError('acquired_at must be timezone-aware')
        if self.expires_at is not None:
            if self.expires_at.tzinfo is None:
                raise ValueError('expires_at must be timezone-aware')
            if self.expires_at <= self.acquired_at:
                raise ValueError('expires_at must be > acquired_at')


class BillingJobLeaseStoreContract(Protocol):
    def acquire(self, lease: BillingJobLease) -> BillingJobLease: ...
    def get(self, *, tenant_id: str, job_name: str, run_key: str) -> BillingJobLease | None: ...
    def renew(self, *, tenant_id: str, job_name: str, run_key: str, fencing_token: str, acquired_at: datetime, lease_ttl: timedelta) -> BillingJobLease: ...
    def release(self, *, tenant_id: str, job_name: str, run_key: str, fencing_token: str) -> bool: ...


class InMemoryBillingJobLeaseStore:
    def __init__(self) -> None:
        self._leases: dict[tuple[str, str, str], BillingJobLease] = {}

    def acquire(self, lease: BillingJobLease) -> BillingJobLease:
        lease.validate()
        key = (require_tenant_id(lease.tenant_id), str(lease.job_name).strip(), str(lease.run_key).strip())
        existing = self._leases.get(key)
        if existing is not None and not self._is_expired(existing, now=lease.acquired_at):
            raise RuntimeError('billing job lease already held')
        self._leases[key] = lease
        return lease

    def get(self, *, tenant_id: str, job_name: str, run_key: str) -> BillingJobLease | None:
        key = (require_tenant_id(tenant_id), str(job_name).strip(), str(run_key).strip())
        lease = self._leases.get(key)
        if lease is None:
            return None
        if self._is_expired(lease, now=utc_now()):
            self._leases.pop(key, None)
            return None
        return lease

    def renew(self, *, tenant_id: str, job_name: str, run_key: str, fencing_token: str, acquired_at: datetime, lease_ttl: timedelta) -> BillingJobLease:
        if acquired_at.tzinfo is None:
            raise ValueError('acquired_at must be timezone-aware')
        if lease_ttl.total_seconds() <= 0:
            raise ValueError('lease_ttl must be > 0')
        key = (require_tenant_id(tenant_id), str(job_name).strip(), str(run_key).strip())
        existing = self._leases.get(key)
        if existing is None or self._is_expired(existing, now=acquired_at):
            raise LookupError('billing job lease not held')
        if str(existing.fencing_token) != str(fencing_token).strip():
            raise RuntimeError('billing job lease fencing mismatch')
        renewed = BillingJobLease(tenant_id=existing.tenant_id, job_name=existing.job_name, run_key=existing.run_key, worker_id=existing.worker_id, fencing_token=existing.fencing_token, acquired_at=acquired_at, expires_at=acquired_at + lease_ttl, metadata=dict(existing.metadata))
        renewed.validate()
        self._leases[key] = renewed
        return renewed

    def release(self, *, tenant_id: str, job_name: str, run_key: str, fencing_token: str) -> bool:
        key = (require_tenant_id(tenant_id), str(job_name).strip(), str(run_key).strip())
        existing = self._leases.get(key)
        if existing is None:
            return False
        if str(existing.fencing_token) != str(fencing_token).strip():
            return False
        self._leases.pop(key, None)
        return True

    @staticmethod
    def _is_expired(lease: BillingJobLease, *, now: datetime) -> bool:
        return lease.expires_at is not None and now >= lease.expires_at


class SqliteBillingJobLeaseStore(PlatformSqliteBillingJobLeaseStore):
    """Billing scheduler-facing lease store facade.

    SQLite ownership lives in runtime.platform.billing_scheduler_lease_store.
    """

    def __init__(self, *, sqlite_path: str) -> None:
        super().__init__(sqlite_path=sqlite_path, lease_cls=BillingJobLease, utc_now_fn=utc_now)


def create_job_lease(*, tenant_id: str, job_name: str, run_key: str, worker_id: str, acquired_at: datetime | None = None, lease_ttl: timedelta | None = None, metadata: dict[str, object] | None = None) -> BillingJobLease:
    observed_at = acquired_at or utc_now()
    if observed_at.tzinfo is None:
        raise ValueError('acquired_at must be timezone-aware')
    if lease_ttl is not None and lease_ttl.total_seconds() <= 0:
        raise ValueError('lease_ttl must be > 0')
    expires_at = None if lease_ttl is None else observed_at + lease_ttl
    lease = BillingJobLease(
        tenant_id=require_tenant_id(tenant_id),
        job_name=str(job_name).strip(),
        run_key=str(run_key).strip(),
        worker_id=str(worker_id).strip(),
        acquired_at=observed_at,
        expires_at=expires_at,
        metadata=dict(metadata or {}),
    )
    lease.validate()
    return lease


__all__ = [
    'CANON_BILLING_JOB_LEASES',
    'CANON_PLATFORM_BILLING_SCHEDULER_LEASE_STORE',
    'LEASE_SCHEMA_VERSION',
    'BillingJobLease',
    'BillingJobLeaseStoreContract',
    'InMemoryBillingJobLeaseStore',
    'SqliteBillingJobLeaseStore',
    'create_job_lease',
]

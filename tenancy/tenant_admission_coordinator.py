from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from core.tenancy.normalization import require_tenant_id
from tenancy.tenant_admission_contract import (
    TenantAdmissionBackend,
    TenantAdmissionLease,
    TenantAdmissionRequest,
    TenantAdmissionVerdict,
)
from tenancy.tenant_contract import TenantPolicyStoreContract
from tenancy.tenant_runtime_lease_store import TenantRuntimeLeaseStore


CANON_TENANT_ADMISSION_COORDINATOR = True


@dataclass(frozen=True)
class LeaseStoreAdmissionBackend(TenantAdmissionBackend):
    lease_store: TenantRuntimeLeaseStore

    def admit(self, *, request: TenantAdmissionRequest, limit: int) -> TenantAdmissionVerdict:
        request.validate()
        result = self.lease_store.acquire(
            tenant_id=request.tenant_id,
            run_id=request.run_id,
            owner_id=request.owner_id,
            limit=limit,
            ttl_seconds=request.ttl_seconds,
            labels=request.labels,
            now=request.requested_at,
        )
        lease = None
        if result.lease is not None:
            lease = TenantAdmissionLease(
                tenant_id=result.lease.tenant_id,
                run_id=result.lease.run_id,
                owner_id=result.lease.owner_id,
                fencing_token=result.lease.fencing_token,
                acquired_at=result.lease.acquired_at,
                expires_at=result.lease.expires_at,
            )
            lease.validate()
        return TenantAdmissionVerdict(
            allowed=result.allowed,
            reason=result.reason,
            tenant_id=result.tenant_id,
            run_id=result.run_id,
            active_runs=result.active_runs,
            limit=result.limit,
            lease=lease,
        )

    def renew(self, *, tenant_id: str, run_id: str, owner_id: str, ttl_seconds: int) -> TenantAdmissionLease:
        record = self.lease_store.renew(
            tenant_id=tenant_id,
            run_id=run_id,
            owner_id=owner_id,
            ttl_seconds=ttl_seconds,
        )
        lease = TenantAdmissionLease(
            tenant_id=record.tenant_id,
            run_id=record.run_id,
            owner_id=record.owner_id,
            fencing_token=record.fencing_token,
            acquired_at=record.acquired_at,
            expires_at=record.expires_at,
        )
        lease.validate()
        return lease

    def release(self, *, tenant_id: str, run_id: str, owner_id: str) -> bool:
        return self.lease_store.release(tenant_id=tenant_id, run_id=run_id, owner_id=owner_id)

    def list_active(self, *, tenant_id: str) -> tuple[TenantAdmissionLease, ...]:
        records = self.lease_store.list_active(tenant_id=tenant_id)
        leases = [
            TenantAdmissionLease(
                tenant_id=item.tenant_id,
                run_id=item.run_id,
                owner_id=item.owner_id,
                fencing_token=item.fencing_token,
                acquired_at=item.acquired_at,
                expires_at=item.expires_at,
            )
            for item in records
        ]
        for lease in leases:
            lease.validate()
        return tuple(leases)


class TenantAdmissionCoordinator:
    def __init__(self, *, policy_store: TenantPolicyStoreContract, backend: TenantAdmissionBackend) -> None:
        self._policy_store = policy_store
        self._backend = backend

    def admit(
        self,
        *,
        tenant_id: str,
        run_id: str,
        owner_id: str,
        ttl_seconds: int,
        labels: Mapping[str, str] | None = None,
    ) -> TenantAdmissionVerdict:
        tid = require_tenant_id(tenant_id)
        limit = self._limit_for(tid)
        request = TenantAdmissionRequest(
            tenant_id=tid,
            run_id=run_id,
            owner_id=owner_id,
            ttl_seconds=ttl_seconds,
            labels=dict(labels or {}),
        )
        request.validate()
        return self._backend.admit(request=request, limit=limit)

    def renew(self, *, tenant_id: str, run_id: str, owner_id: str, ttl_seconds: int) -> TenantAdmissionLease:
        return self._backend.renew(
            tenant_id=require_tenant_id(tenant_id),
            run_id=run_id,
            owner_id=owner_id,
            ttl_seconds=ttl_seconds,
        )

    def release(self, *, tenant_id: str, run_id: str, owner_id: str) -> bool:
        return self._backend.release(tenant_id=require_tenant_id(tenant_id), run_id=run_id, owner_id=owner_id)

    def list_active(self, *, tenant_id: str) -> tuple[TenantAdmissionLease, ...]:
        return self._backend.list_active(tenant_id=require_tenant_id(tenant_id))

    def _limit_for(self, tenant_id: str) -> int:
        bundle = self._policy_store.require(tenant_id)
        runtime_limits = getattr(bundle, 'runtime_limits', None)
        if runtime_limits is None:
            raise AttributeError('policy bundle must expose runtime_limits')
        raw = getattr(runtime_limits, 'max_concurrent_runs', None)
        if raw is None:
            raise AttributeError('runtime_limits must expose max_concurrent_runs')
        return max(0, int(raw))


__all__ = [
    'CANON_TENANT_ADMISSION_COORDINATOR',
    'LeaseStoreAdmissionBackend',
    'TenantAdmissionCoordinator',
]

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Mapping

from core.tenancy.normalization import require_tenant_id
from tenancy.tenant_backend_clock_policy import ensure_aware, utc_now
from tenancy.tenant_runtime_reconciliation import TenantRuntimeReconciler, TenantRuntimeReconciliationResult
from tenancy.tenant_runtime_lease_store import TenantRuntimeLeaseStore


CANON_TENANT_RUNTIME_LEASE_RECOVERY = True


@dataclass(frozen=True)
class TenantRuntimeRecoveryPlan:
    tenant_id: str
    limit: int
    ttl_seconds: int
    owner_id: str
    labels: Mapping[str, str]

    def validate(self) -> None:
        require_tenant_id(self.tenant_id)
        if int(self.limit) < 0:
            raise ValueError('limit must be >= 0')
        if int(self.ttl_seconds) <= 0:
            raise ValueError('ttl_seconds must be > 0')
        if not str(self.owner_id or '').strip():
            raise ValueError('owner_id is required')
        for key, value in dict(self.labels).items():
            if not str(key or '').strip() or not str(value or '').strip():
                raise ValueError('labels must be non-empty')


@dataclass(frozen=True)
class TenantRuntimeRecoveryResult:
    tenant_id: str
    reconciliation: TenantRuntimeReconciliationResult
    reacquired_runs: tuple[str, ...]
    denied_runs: tuple[str, ...]


class TenantRuntimeLeaseRecoveryService:
    def __init__(
        self,
        *,
        lease_store: TenantRuntimeLeaseStore,
        reconciler: TenantRuntimeReconciler,
    ) -> None:
        self._lease_store = lease_store
        self._reconciler = reconciler

    def recover(
        self,
        *,
        plan: TenantRuntimeRecoveryPlan,
        desired_runs: tuple[str, ...],
        now: datetime | None = None,
    ) -> TenantRuntimeRecoveryResult:
        plan.validate()
        moment = ensure_aware(now or utc_now())
        reconciliation = self._reconciler.reconcile(tenant_id=plan.tenant_id, limit=plan.limit, now=moment)
        reacquired: list[str] = []
        denied: list[str] = []
        seen: set[str] = set()
        for run_id in desired_runs:
            normalized = str(run_id or '').strip()
            if not normalized:
                raise ValueError('desired run_id must be non-empty')
            if normalized in seen:
                continue
            seen.add(normalized)
            result = self._lease_store.acquire(
                tenant_id=plan.tenant_id,
                run_id=normalized,
                owner_id=plan.owner_id,
                limit=plan.limit,
                ttl_seconds=plan.ttl_seconds,
                labels=dict(plan.labels),
                now=moment,
            )
            if result.allowed and result.lease is not None:
                reacquired.append(normalized)
            else:
                denied.append(normalized)
        return TenantRuntimeRecoveryResult(
            tenant_id=plan.tenant_id,
            reconciliation=reconciliation,
            reacquired_runs=tuple(reacquired),
            denied_runs=tuple(denied),
        )


__all__ = [
    'CANON_TENANT_RUNTIME_LEASE_RECOVERY',
    'TenantRuntimeLeaseRecoveryService',
    'TenantRuntimeRecoveryPlan',
    'TenantRuntimeRecoveryResult',
]

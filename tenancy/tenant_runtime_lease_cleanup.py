from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from tenancy.tenant_runtime_lease_store import TenantRuntimeLeaseRecord, TenantRuntimeLeaseStore, ensure_aware, utc_now


CANON_TENANT_RUNTIME_LEASE_CLEANUP = True


class TenantLeaseCleanupObserver(Protocol):
    def on_runtime_leases_reaped(self, *, leases: tuple[TenantRuntimeLeaseRecord, ...]) -> None: ...


@dataclass(frozen=True)
class TenantRuntimeLeaseCleanupReport:
    reaped_count: int
    reaped_tenants: tuple[str, ...]
    reaped_run_ids: tuple[str, ...]
    executed_at: datetime


class TenantRuntimeLeaseCleanupService:
    def __init__(self, *, store: TenantRuntimeLeaseStore, observer: TenantLeaseCleanupObserver | None = None) -> None:
        self._store = store
        self._observer = observer

    def run_once(self, *, now: datetime | None = None) -> TenantRuntimeLeaseCleanupReport:
        moment = ensure_aware(now or utc_now())
        reaped = tuple(self._store.reap_expired(now=moment))
        if self._observer is not None and reaped:
            self._observer.on_runtime_leases_reaped(leases=reaped)
        tenants = tuple(sorted({item.tenant_id for item in reaped}))
        run_ids = tuple(sorted(item.run_id for item in reaped))
        return TenantRuntimeLeaseCleanupReport(
            reaped_count=len(reaped),
            reaped_tenants=tenants,
            reaped_run_ids=run_ids,
            executed_at=moment,
        )


__all__ = [
    'CANON_TENANT_RUNTIME_LEASE_CLEANUP',
    'TenantLeaseCleanupObserver',
    'TenantRuntimeLeaseCleanupReport',
    'TenantRuntimeLeaseCleanupService',
]

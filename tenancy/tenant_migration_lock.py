from __future__ import annotations

from dataclasses import dataclass

from core.tenancy.normalization import require_tenant_id
from tenancy.tenant_contract import TenantRegistryContract
from tenancy.tenant_migration_lock_backend import TenantMigrationLockBackend, TenantMigrationLockRecord


CANON_TENANT_MIGRATION_LOCK = True


@dataclass(frozen=True)
class TenantMigrationLockVerdict:
    allowed: bool
    reason: str
    tenant_id: str
    lock: TenantMigrationLockRecord | None = None


class TenantMigrationLockService:
    def __init__(self, *, backend: TenantMigrationLockBackend, tenant_registry: TenantRegistryContract | None = None) -> None:
        self._backend = backend
        self._tenant_registry = tenant_registry

    def acquire(self, *, tenant_id: str, operation_id: str, owner_id: str, ttl_seconds: int) -> TenantMigrationLockVerdict:
        tid = require_tenant_id(tenant_id)
        if self._tenant_registry is not None:
            self._tenant_registry.require(tid)
        lock = self._backend.acquire(tenant_id=tid, operation_id=operation_id, owner_id=owner_id, ttl_seconds=ttl_seconds)
        if lock is None:
            current = self._backend.get(tenant_id=tid)
            return TenantMigrationLockVerdict(False, 'tenant_migration_locked', tid, current)
        return TenantMigrationLockVerdict(True, 'acquired', tid, lock)

    def renew(self, *, tenant_id: str, operation_id: str, owner_id: str, ttl_seconds: int) -> TenantMigrationLockRecord:
        return self._backend.renew(tenant_id=require_tenant_id(tenant_id), operation_id=operation_id, owner_id=owner_id, ttl_seconds=ttl_seconds)

    def release(self, *, tenant_id: str, operation_id: str, owner_id: str) -> bool:
        return self._backend.release(tenant_id=require_tenant_id(tenant_id), operation_id=operation_id, owner_id=owner_id)

    def get(self, *, tenant_id: str) -> TenantMigrationLockRecord | None:
        return self._backend.get(tenant_id=require_tenant_id(tenant_id))


__all__ = ['CANON_TENANT_MIGRATION_LOCK', 'TenantMigrationLockService', 'TenantMigrationLockVerdict']

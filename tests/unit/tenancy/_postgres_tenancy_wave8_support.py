from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from tenancy.tenant_admission_contract import TenantAdmissionRequest
from tenancy.tenant_admission_postgres import (
    PostgresTenantAdmissionBackend,
    PostgresTenantAdmissionBackendConfig,
    _advisory_lock_key as admission_lock_key,
    _safe_identifier as admission_identifier,
)
from tenancy.tenant_migration_lock_postgres import (
    PostgresTenantMigrationLockBackend,
    PostgresTenantMigrationLockBackendConfig,
    _advisory_lock_key as migration_lock_key,
    _safe_identifier as migration_identifier,
)
from tenancy.tenant_runtime_lease_postgres import (
    PostgresTenantRuntimeLeaseStore,
    PostgresTenantRuntimeLeaseStoreConfig,
    _advisory_lock_key as runtime_lock_key,
    _safe_identifier as runtime_identifier,
)

UTC = timezone.utc
NOW = datetime(2026, 7, 20, 12, 0, tzinfo=UTC)


@dataclass
class Step:
    contains: str
    one: Any = None
    all: Any = None


class Cursor:
    def __init__(self, steps: list[Step]) -> None:
        self.steps = list(steps)
        self.executed: list[tuple[str, tuple[Any, ...]]] = []
        self.current: Step | None = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def execute(self, sql: str, params: tuple[Any, ...] = ()) -> None:
        compact = " ".join(sql.split())
        assert self.steps, f"unexpected SQL: {compact} {params!r}"
        step = self.steps.pop(0)
        assert step.contains in compact, (step.contains, compact)
        self.executed.append((compact, tuple(params)))
        self.current = step

    def fetchone(self):
        assert self.current is not None
        return self.current.one

    def fetchall(self):
        assert self.current is not None
        return [] if self.current.all is None else self.current.all


class Connection:
    def __init__(self, steps: list[Step]) -> None:
        self.cur = Cursor(steps)
        self.commits = 0

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def cursor(self):
        return self.cur

    def commit(self) -> None:
        self.commits += 1


class Connector:
    def __init__(self, *connections: Connection) -> None:
        self.connections = list(connections)

    def __call__(self):
        assert self.connections
        return self.connections.pop(0)


def runtime_backend(*connections: Connection) -> PostgresTenantRuntimeLeaseStore:
    backend = object.__new__(PostgresTenantRuntimeLeaseStore)
    backend._config = PostgresTenantRuntimeLeaseStoreConfig("postgres://test")
    backend._connect = Connector(*connections)
    return backend


def admission_backend(*connections: Connection) -> PostgresTenantAdmissionBackend:
    backend = object.__new__(PostgresTenantAdmissionBackend)
    backend._config = PostgresTenantAdmissionBackendConfig("postgres://test")
    backend._connect = Connector(*connections)
    return backend


def migration_backend(*connections: Connection) -> PostgresTenantMigrationLockBackend:
    backend = object.__new__(PostgresTenantMigrationLockBackend)
    backend._config = PostgresTenantMigrationLockBackendConfig("postgres://test")
    backend._connect = Connector(*connections)
    return backend


def runtime_row(
    *,
    tenant: str = "tenant-a",
    run: str = "run-1",
    owner: str = "owner-1",
    token: int = 1,
    acquired: datetime = NOW,
    heartbeat: datetime = NOW,
    expires: datetime = NOW + timedelta(minutes=5),
    labels: Any = None,
):
    return (
        tenant,
        run,
        owner,
        f"tenant/{tenant}/runtime/{run}",
        token,
        acquired,
        heartbeat,
        expires,
        {} if labels is None else labels,
    )


def admission_request(**overrides: Any) -> TenantAdmissionRequest:
    values = {
        "tenant_id": "tenant-a",
        "run_id": "run-1",
        "owner_id": "owner-1",
        "ttl_seconds": 60,
        "labels": {"kind": "worker"},
        "requested_at": NOW,
    }
    values.update(overrides)
    return TenantAdmissionRequest(**values)


def migration_row(
    *,
    tenant: str = "tenant-a",
    operation: str = "op-1",
    owner: str = "owner-1",
    token: int = 1,
    acquired: datetime = NOW,
    expires: datetime = NOW + timedelta(minutes=5),
):
    return (tenant, operation, owner, token, acquired, expires)


__all__ = [
    "Connection",
    "Connector",
    "Cursor",
    "NOW",
    "PostgresTenantAdmissionBackendConfig",
    "PostgresTenantMigrationLockBackendConfig",
    "PostgresTenantRuntimeLeaseStoreConfig",
    "Step",
    "UTC",
    "admission_backend",
    "admission_identifier",
    "admission_lock_key",
    "admission_request",
    "migration_backend",
    "migration_identifier",
    "migration_lock_key",
    "migration_row",
    "runtime_backend",
    "runtime_identifier",
    "runtime_lock_key",
    "runtime_row",
]

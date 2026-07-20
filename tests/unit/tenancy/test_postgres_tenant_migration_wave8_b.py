from __future__ import annotations

import sys
from types import SimpleNamespace

import pytest

from tenancy.tenant_admission_postgres import (
    PostgresTenantAdmissionBackend,
    PostgresTenantAdmissionBackendConfig,
)
from tenancy.tenant_migration_lock_postgres import (
    PostgresTenantMigrationLockBackend,
    PostgresTenantMigrationLockBackendConfig,
)
from tenancy.tenant_runtime_lease_postgres import (
    PostgresTenantRuntimeLeaseStore,
    PostgresTenantRuntimeLeaseStoreConfig,
)
from tests.unit.tenancy._postgres_tenancy_wave8_support import (
    Connection,
    Cursor,
    NOW,
    Step,
    admission_backend,
    admission_lock_key,
    migration_backend,
    migration_lock_key,
    runtime_backend,
    runtime_lock_key,
    runtime_row,
)


class PsycopgStub:
    def __init__(self, connection: Connection) -> None:
        self.connection = connection
        self.dsns: list[str] = []

    def connect(self, dsn: str):
        self.dsns.append(dsn)
        return self.connection


def _negative_tenant(fn) -> str:
    for index in range(10_000):
        tenant = f"tenant-negative-{index}"
        if fn(namespace="ns", tenant_id=tenant) < 0:
            return tenant
    raise AssertionError("unable to produce signed negative advisory key")


def test_signed_advisory_negative_branch():
    for fn in (runtime_lock_key, admission_lock_key, migration_lock_key):
        tenant = _negative_tenant(fn)
        assert fn(namespace="ns", tenant_id=tenant) < 0


def test_postgres_backend_constructors_and_schema(monkeypatch):
    cases = [
        (
            PostgresTenantRuntimeLeaseStore,
            PostgresTenantRuntimeLeaseStoreConfig("runtime-dsn"),
            Connection([
                Step("CREATE TABLE IF NOT EXISTS tenant_runtime_leases"),
                Step("CREATE INDEX IF NOT EXISTS ix_tenant_runtime_leases_expires_at"),
                Step("CREATE TABLE IF NOT EXISTS tenant_runtime_lease_tokens"),
            ]),
        ),
        (
            PostgresTenantAdmissionBackend,
            PostgresTenantAdmissionBackendConfig("admission-dsn"),
            Connection([
                Step("CREATE TABLE IF NOT EXISTS tenant_admission_leases"),
                Step("CREATE INDEX IF NOT EXISTS ix_tenant_admission_leases_expires_at"),
                Step("CREATE TABLE IF NOT EXISTS tenant_admission_fencing"),
            ]),
        ),
        (
            PostgresTenantMigrationLockBackend,
            PostgresTenantMigrationLockBackendConfig("migration-dsn"),
            Connection([
                Step("CREATE TABLE IF NOT EXISTS tenant_migration_locks"),
                Step("CREATE INDEX IF NOT EXISTS ix_tenant_migration_locks_expires_at"),
                Step("CREATE TABLE IF NOT EXISTS tenant_migration_lock_tokens"),
            ]),
        ),
    ]
    for cls, config, conn in cases:
        stub = PsycopgStub(conn)
        monkeypatch.setitem(sys.modules, "psycopg", SimpleNamespace(connect=stub.connect))
        instance = cls(config)
        assert instance._config == config
        assert stub.dsns == [config.dsn]
        assert conn.commits == 1
        assert conn.cur.steps == []


def test_runtime_get_none_and_short_row_labels():
    conn = Connection([
        Step("pg_advisory_xact_lock"),
        Step("WHERE tenant_id = %s AND expires_at <= %s", all=[]),
        Step("DELETE FROM tenant_runtime_leases WHERE tenant_id = %s AND expires_at <= %s"),
        Step("WHERE tenant_id = %s AND run_id = %s", one=None),
    ])
    assert runtime_backend(conn).get(tenant_id="tenant-a", run_id="run-1") is None
    short = runtime_row()[:8]
    assert PostgresTenantRuntimeLeaseStore._row_to_record(short).labels == {}


def test_admission_invalid_inputs_and_owner_mismatch():
    backend = admission_backend()
    with pytest.raises(ValueError, match="run_id and owner_id"):
        backend.renew(
            tenant_id="tenant-a",
            run_id="",
            owner_id="owner",
            ttl_seconds=1,
        )
    with pytest.raises(ValueError, match="run_id and owner_id"):
        backend.release(tenant_id="tenant-a", run_id="run", owner_id="")
    with pytest.raises(ValueError, match="ttl_seconds"):
        backend._renew_locked(
            Cursor([]),
            tenant_id="tenant-a",
            run_id="run",
            owner_id="owner",
            ttl_seconds=0,
            now=NOW,
        )

    mismatch = Connection([
        Step("pg_advisory_xact_lock"),
        Step("DELETE FROM tenant_admission_leases WHERE tenant_id = %s AND expires_at <= %s"),
        Step("SELECT owner_id", one=("other",)),
    ])
    with pytest.raises(PermissionError):
        admission_backend(mismatch).release(
            tenant_id="tenant-a",
            run_id="run",
            owner_id="owner",
        )
    with pytest.raises(TypeError, match="datetime"):
        PostgresTenantAdmissionBackend._ensure_aware("bad", field_name="now")


def test_migration_invalid_inputs_owner_mismatch_and_existing_token():
    backend = migration_backend()
    for method, kwargs in (
        (
            backend.acquire,
            dict(
                tenant_id="tenant-a",
                operation_id="",
                owner_id="owner",
                ttl_seconds=1,
                now=NOW,
            ),
        ),
        (
            backend.acquire,
            dict(
                tenant_id="tenant-a",
                operation_id="op",
                owner_id="owner",
                ttl_seconds=0,
                now=NOW,
            ),
        ),
        (
            backend.renew,
            dict(
                tenant_id="tenant-a",
                operation_id="",
                owner_id="owner",
                ttl_seconds=1,
                now=NOW,
            ),
        ),
        (
            backend.renew,
            dict(
                tenant_id="tenant-a",
                operation_id="op",
                owner_id="owner",
                ttl_seconds=0,
                now=NOW,
            ),
        ),
        (
            backend.release,
            dict(tenant_id="tenant-a", operation_id="", owner_id="owner"),
        ),
    ):
        with pytest.raises(ValueError):
            method(**kwargs)

    mismatch = Connection([
        Step("pg_advisory_xact_lock"),
        Step("DELETE FROM tenant_migration_locks WHERE tenant_id = %s AND expires_at <= %s"),
        Step("SELECT operation_id", one=("other", "owner")),
    ])
    with pytest.raises(PermissionError):
        migration_backend(mismatch).release(
            tenant_id="tenant-a",
            operation_id="op",
            owner_id="owner",
        )

    cur = Cursor([
        Step("SELECT next_token", one=(8,)),
        Step("INSERT INTO tenant_migration_lock_tokens"),
    ])
    assert backend._next_token_locked(cur, tenant_id="tenant-a") == 9


def test_signed_advisory_positive_branch():
    for fn in (runtime_lock_key, admission_lock_key, migration_lock_key):
        assert fn(namespace="ns", tenant_id="p3") >= 0

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from tests.unit.tenancy._postgres_tenancy_wave8_support import (
    Connection,
    Cursor,
    NOW,
    Step,
    admission_backend,
    migration_backend,
    migration_row,
)


def test_migration_acquire_new_and_existing_paths():
    new_conn = Connection([
        Step("pg_advisory_xact_lock"),
        Step("DELETE FROM tenant_migration_locks WHERE tenant_id = %s AND expires_at <= %s"),
        Step("WHERE tenant_id = %s FOR UPDATE", one=None),
        Step("SELECT next_token", one=None),
        Step("INSERT INTO tenant_migration_lock_tokens"),
        Step("INSERT INTO tenant_migration_locks"),
    ])
    lock = migration_backend(new_conn).acquire(
        tenant_id="tenant-a",
        operation_id="op-1",
        owner_id="owner-1",
        ttl_seconds=60,
        now=NOW,
    )
    assert lock and lock.fencing_token == 1

    existing = migration_row()
    same_conn = Connection([
        Step("pg_advisory_xact_lock"),
        Step("DELETE FROM tenant_migration_locks WHERE tenant_id = %s AND expires_at <= %s"),
        Step("WHERE tenant_id = %s FOR UPDATE", one=existing),
        Step("UPDATE tenant_migration_locks SET expires_at"),
    ])
    assert migration_backend(same_conn).acquire(
        tenant_id="tenant-a",
        operation_id="op-1",
        owner_id="owner-1",
        ttl_seconds=30,
        now=NOW,
    ).fencing_token == 1

    other_conn = Connection([
        Step("pg_advisory_xact_lock"),
        Step("DELETE FROM tenant_migration_locks WHERE tenant_id = %s AND expires_at <= %s"),
        Step("WHERE tenant_id = %s FOR UPDATE", one=migration_row(operation="other")),
    ])
    assert migration_backend(other_conn).acquire(
        tenant_id="tenant-a",
        operation_id="op-1",
        owner_id="owner-1",
        ttl_seconds=30,
        now=NOW,
    ) is None


@pytest.mark.parametrize(
    ("row", "exc"),
    [
        (None, KeyError),
        (("other", "owner-1", 1, NOW, NOW + timedelta(minutes=1)), PermissionError),
        (("op-1", "owner-1", 1, NOW, NOW), KeyError),
    ],
)
def test_migration_renew_failures(row, exc):
    conn = Connection([
        Step("pg_advisory_xact_lock"),
        Step("DELETE FROM tenant_migration_locks WHERE tenant_id = %s AND expires_at <= %s"),
        Step("WHERE tenant_id = %s FOR UPDATE", one=row),
    ])
    with pytest.raises(exc):
        migration_backend(conn).renew(
            tenant_id="tenant-a",
            operation_id="op-1",
            owner_id="owner-1",
            ttl_seconds=30,
            now=NOW,
        )


def test_migration_renew_release_get_and_datetime_contract():
    renew = Connection([
        Step("pg_advisory_xact_lock"),
        Step("DELETE FROM tenant_migration_locks WHERE tenant_id = %s AND expires_at <= %s"),
        Step(
            "WHERE tenant_id = %s FOR UPDATE",
            one=("op-1", "owner-1", 3, NOW, NOW + timedelta(minutes=1)),
        ),
        Step("UPDATE tenant_migration_locks SET expires_at"),
    ])
    assert migration_backend(renew).renew(
        tenant_id="tenant-a",
        operation_id="op-1",
        owner_id="owner-1",
        ttl_seconds=30,
        now=NOW,
    ).fencing_token == 3

    missing = Connection([
        Step("pg_advisory_xact_lock"),
        Step("DELETE FROM tenant_migration_locks WHERE tenant_id = %s AND expires_at <= %s"),
        Step("SELECT operation_id", one=None),
    ])
    assert migration_backend(missing).release(
        tenant_id="tenant-a",
        operation_id="op-1",
        owner_id="owner-1",
    ) is False

    success = Connection([
        Step("pg_advisory_xact_lock"),
        Step("DELETE FROM tenant_migration_locks WHERE tenant_id = %s AND expires_at <= %s"),
        Step("SELECT operation_id", one=("op-1", "owner-1")),
        Step("DELETE FROM tenant_migration_locks WHERE tenant_id = %s"),
    ])
    assert migration_backend(success).release(
        tenant_id="tenant-a",
        operation_id="op-1",
        owner_id="owner-1",
    ) is True

    get_conn = Connection([
        Step("pg_advisory_xact_lock"),
        Step("DELETE FROM tenant_migration_locks WHERE tenant_id = %s AND expires_at <= %s"),
        Step("WHERE tenant_id = %s", one=migration_row()),
    ])
    assert migration_backend(get_conn).get(tenant_id="tenant-a").operation_id == "op-1"

    none_conn = Connection([
        Step("pg_advisory_xact_lock"),
        Step("DELETE FROM tenant_migration_locks WHERE tenant_id = %s AND expires_at <= %s"),
        Step("WHERE tenant_id = %s", one=None),
    ])
    assert migration_backend(none_conn).get(tenant_id="tenant-a") is None
    with pytest.raises(ValueError, match="timezone-aware"):
        migration_backend().acquire(
            tenant_id="tenant-a",
            operation_id="op-1",
            owner_id="owner-1",
            ttl_seconds=30,
            now=datetime(2026, 1, 1),
        )


def test_global_vs_scoped_reaping_contracts():
    for backend in (admission_backend(), migration_backend()):
        scoped = Cursor([Step("WHERE tenant_id = %s AND expires_at <= %s")])
        backend._reap_expired_locked(scoped, now=NOW, tenant_id="tenant-a")
        assert scoped.executed[0][1] == ("tenant-a", NOW)
        global_cur = Cursor([Step("WHERE expires_at <= %s")])
        backend._reap_expired_locked(global_cur, now=NOW)
        assert global_cur.executed[0][1] == (NOW,)

from __future__ import annotations

from datetime import timedelta

import pytest

from tests.unit.tenancy._postgres_tenancy_wave8_support import (
    Connection,
    NOW,
    Step,
    runtime_backend,
    runtime_row,
)


def test_runtime_acquire_new_and_scoped_reap():
    row = runtime_row(labels={"kind": "worker"})
    conn = Connection([
        Step("pg_advisory_xact_lock"),
        Step("WHERE tenant_id = %s AND expires_at <= %s", all=[]),
        Step("DELETE FROM tenant_runtime_leases WHERE tenant_id = %s AND expires_at <= %s"),
        Step("WHERE tenant_id = %s AND run_id = %s FOR UPDATE", one=None),
        Step("SELECT COUNT(*)", one=(0,)),
        Step("SELECT next_token", one=None),
        Step("INSERT INTO tenant_runtime_lease_tokens"),
        Step("INSERT INTO tenant_runtime_leases"),
        Step("WHERE tenant_id = %s AND run_id = %s", one=row),
    ])
    result = runtime_backend(conn).acquire(
        tenant_id="tenant-a",
        run_id="run-1",
        owner_id="owner-1",
        limit=2,
        ttl_seconds=60,
        labels={"kind": "worker"},
        now=NOW,
    )
    assert result.allowed and result.reason == "acquired"
    assert result.active_runs == 1 and result.lease.fencing_token == 1
    assert conn.commits == 1
    assert conn.cur.executed[1][1] == ("tenant-a", NOW)


@pytest.mark.parametrize(
    ("owner", "labels", "reason"),
    [
        ("other", {"kind": "worker"}, "lease_owned_by_another_owner"),
        ("owner-1", {"kind": "other"}, "lease_labels_mismatch"),
    ],
)
def test_runtime_acquire_existing_rejections(owner, labels, reason):
    conn = Connection([
        Step("pg_advisory_xact_lock"),
        Step("WHERE tenant_id = %s AND expires_at <= %s", all=[]),
        Step("DELETE FROM tenant_runtime_leases WHERE tenant_id = %s AND expires_at <= %s"),
        Step(
            "WHERE tenant_id = %s AND run_id = %s FOR UPDATE",
            one=runtime_row(owner=owner, labels=labels),
        ),
        Step("SELECT COUNT(*)", one=(1,)),
    ])
    result = runtime_backend(conn).acquire(
        tenant_id="tenant-a",
        run_id="run-1",
        owner_id="owner-1",
        limit=2,
        ttl_seconds=60,
        labels={"kind": "worker"},
        now=NOW,
    )
    assert not result.allowed and result.reason == reason
    assert conn.commits == 1


def test_runtime_acquire_existing_renews():
    old = runtime_row(labels={"kind": "worker"})
    renewed = runtime_row(
        heartbeat=NOW,
        expires=NOW + timedelta(seconds=90),
        labels={"kind": "worker"},
    )
    conn = Connection([
        Step("pg_advisory_xact_lock"),
        Step("WHERE tenant_id = %s AND expires_at <= %s", all=[]),
        Step("DELETE FROM tenant_runtime_leases WHERE tenant_id = %s AND expires_at <= %s"),
        Step("WHERE tenant_id = %s AND run_id = %s FOR UPDATE", one=old),
        Step("SELECT COUNT(*)", one=(1,)),
        Step("UPDATE tenant_runtime_leases SET heartbeat_at", one=None),
        Step("WHERE tenant_id = %s AND run_id = %s", one=renewed),
    ])
    result = runtime_backend(conn).acquire(
        tenant_id="tenant-a",
        run_id="run-1",
        owner_id="owner-1",
        limit=2,
        ttl_seconds=90,
        labels={"kind": "worker"},
        now=NOW,
    )
    assert result.allowed and result.reason == "already_acquired"
    assert result.lease.expires_at == NOW + timedelta(seconds=90)


@pytest.mark.parametrize(
    ("limit", "active", "reason"),
    [(0, 0, "tenant_runtime_disabled"), (1, 1, "tenant_runtime_capacity_exceeded")],
)
def test_runtime_acquire_capacity_rejections(limit, active, reason):
    conn = Connection([
        Step("pg_advisory_xact_lock"),
        Step("WHERE tenant_id = %s AND expires_at <= %s", all=[]),
        Step("DELETE FROM tenant_runtime_leases WHERE tenant_id = %s AND expires_at <= %s"),
        Step("WHERE tenant_id = %s AND run_id = %s FOR UPDATE", one=None),
        Step("SELECT COUNT(*)", one=(active,)),
    ])
    result = runtime_backend(conn).acquire(
        tenant_id="tenant-a",
        run_id="run-1",
        owner_id="owner-1",
        limit=limit,
        ttl_seconds=60,
        now=NOW,
    )
    assert not result.allowed and result.reason == reason


def test_runtime_acquire_insert_must_persist():
    conn = Connection([
        Step("pg_advisory_xact_lock"),
        Step("WHERE tenant_id = %s AND expires_at <= %s", all=[]),
        Step("DELETE FROM tenant_runtime_leases WHERE tenant_id = %s AND expires_at <= %s"),
        Step("WHERE tenant_id = %s AND run_id = %s FOR UPDATE", one=None),
        Step("SELECT COUNT(*)", one=None),
        Step("SELECT next_token", one=(4,)),
        Step("INSERT INTO tenant_runtime_lease_tokens"),
        Step("INSERT INTO tenant_runtime_leases"),
        Step("WHERE tenant_id = %s AND run_id = %s", one=None),
    ])
    with pytest.raises(RuntimeError, match="insert did not persist"):
        runtime_backend(conn).acquire(
            tenant_id="tenant-a",
            run_id="run-1",
            owner_id="owner-1",
            limit=1,
            ttl_seconds=60,
            now=NOW,
        )

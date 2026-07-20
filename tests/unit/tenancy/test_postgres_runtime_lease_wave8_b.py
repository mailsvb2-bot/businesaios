from __future__ import annotations

from datetime import timedelta

import pytest

from tenancy.tenant_runtime_lease_postgres import PostgresTenantRuntimeLeaseStore
from tests.unit.tenancy._postgres_tenancy_wave8_support import (
    Connection,
    NOW,
    Step,
    runtime_backend,
    runtime_row,
)


@pytest.mark.parametrize(
    ("row", "exc"),
    [
        (None, KeyError),
        (runtime_row(owner="other"), PermissionError),
        (
            runtime_row(
                acquired=NOW - timedelta(minutes=3),
                heartbeat=NOW - timedelta(minutes=2),
                expires=NOW,
            ),
            KeyError,
        ),
    ],
)
def test_runtime_renew_failures(row, exc):
    conn = Connection([
        Step("pg_advisory_xact_lock"),
        Step("WHERE tenant_id = %s AND expires_at <= %s", all=[]),
        Step("DELETE FROM tenant_runtime_leases WHERE tenant_id = %s AND expires_at <= %s"),
        Step("WHERE tenant_id = %s AND run_id = %s FOR UPDATE", one=row),
    ])
    with pytest.raises(exc):
        runtime_backend(conn).renew(
            tenant_id="tenant-a",
            run_id="run-1",
            owner_id="owner-1",
            ttl_seconds=60,
            now=NOW,
        )


def test_runtime_renew_success_and_lost_record():
    current = runtime_row()
    renewed = runtime_row(heartbeat=NOW, expires=NOW + timedelta(seconds=60))
    success = Connection([
        Step("pg_advisory_xact_lock"),
        Step("WHERE tenant_id = %s AND expires_at <= %s", all=[]),
        Step("DELETE FROM tenant_runtime_leases WHERE tenant_id = %s AND expires_at <= %s"),
        Step("WHERE tenant_id = %s AND run_id = %s FOR UPDATE", one=current),
        Step("UPDATE tenant_runtime_leases SET heartbeat_at"),
        Step("WHERE tenant_id = %s AND run_id = %s", one=renewed),
    ])
    assert runtime_backend(success).renew(
        tenant_id="tenant-a",
        run_id="run-1",
        owner_id="owner-1",
        ttl_seconds=60,
        now=NOW,
    ).expires_at == renewed[7]

    lost = Connection([
        Step("UPDATE tenant_runtime_leases SET heartbeat_at"),
        Step("WHERE tenant_id = %s AND run_id = %s", one=None),
    ])
    backend = runtime_backend()
    with pytest.raises(RuntimeError, match="renew lost record"):
        backend._renew_locked(
            lost.cur,
            current=backend._row_to_record(current),
            ttl_seconds=60,
            now=NOW,
        )


@pytest.mark.parametrize(
    ("row", "expected", "exc"),
    [(None, False, None), (("other",), None, PermissionError), (("owner-1",), True, None)],
)
def test_runtime_release(row, expected, exc):
    steps = [
        Step("pg_advisory_xact_lock"),
        Step("WHERE tenant_id = %s AND expires_at <= %s", all=[]),
        Step("DELETE FROM tenant_runtime_leases WHERE tenant_id = %s AND expires_at <= %s"),
        Step("SELECT owner_id", one=row),
    ]
    if row == ("owner-1",):
        steps.append(Step("DELETE FROM tenant_runtime_leases WHERE tenant_id = %s AND run_id = %s"))
    conn = Connection(steps)
    backend = runtime_backend(conn)
    if exc:
        with pytest.raises(exc):
            backend.release(tenant_id="tenant-a", run_id="run-1", owner_id="owner-1")
    else:
        assert backend.release(
            tenant_id="tenant-a",
            run_id="run-1",
            owner_id="owner-1",
        ) is expected


def test_runtime_get_list_reap_and_helpers():
    record = runtime_row(labels='{"kind":"worker"}')
    get_conn = Connection([
        Step("pg_advisory_xact_lock"),
        Step("WHERE tenant_id = %s AND expires_at <= %s", all=[]),
        Step("DELETE FROM tenant_runtime_leases WHERE tenant_id = %s AND expires_at <= %s"),
        Step("WHERE tenant_id = %s AND run_id = %s", one=record),
    ])
    assert runtime_backend(get_conn).get(
        tenant_id="tenant-a",
        run_id="run-1",
    ).labels == {"kind": "worker"}

    list_conn = Connection([
        Step("pg_advisory_xact_lock"),
        Step("WHERE tenant_id = %s AND expires_at <= %s", all=[]),
        Step("DELETE FROM tenant_runtime_leases WHERE tenant_id = %s AND expires_at <= %s"),
        Step("WHERE tenant_id = %s ORDER BY acquired_at", all=[record]),
    ])
    assert len(runtime_backend(list_conn).list_active(tenant_id="tenant-a", now=NOW)) == 1

    reap_conn = Connection([
        Step("WHERE expires_at <= %s", all=[record]),
        Step("DELETE FROM tenant_runtime_leases WHERE expires_at <= %s"),
    ])
    assert len(runtime_backend(reap_conn).reap_expired(now=NOW)) == 1
    assert reap_conn.cur.executed[0][1] == (NOW,)
    with pytest.raises(ValueError, match="labels_json"):
        PostgresTenantRuntimeLeaseStore._row_to_record(runtime_row(labels=["bad"]))

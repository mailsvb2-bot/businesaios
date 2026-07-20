from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from tenancy.tenant_admission_postgres import PostgresTenantAdmissionBackend
from tests.unit.tenancy._postgres_tenancy_wave8_support import (
    Connection,
    Cursor,
    NOW,
    Step,
    UTC,
    admission_backend,
    admission_request,
)


def test_admission_accepts_decoded_jsonb_and_renews():
    req = admission_request()
    conn = Connection([
        Step("pg_advisory_xact_lock"),
        Step("DELETE FROM tenant_admission_leases WHERE tenant_id = %s AND expires_at <= %s"),
        Step(
            "WHERE tenant_id = %s AND run_id = %s FOR UPDATE",
            one=("owner-1", {"kind": "worker"}, 3, NOW, NOW + timedelta(minutes=1)),
        ),
        Step("SELECT COUNT(*)", one=(1,)),
        Step(
            "SELECT owner_id, fencing_token",
            one=("owner-1", 3, NOW, NOW + timedelta(minutes=1)),
        ),
        Step("UPDATE tenant_admission_leases SET heartbeat_at"),
    ])
    verdict = admission_backend(conn).admit(request=req, limit=2)
    assert verdict.allowed and verdict.reason == "already_acquired"
    assert verdict.lease.fencing_token == 3


@pytest.mark.parametrize(
    ("row", "reason"),
    [
        (
            ("other", {"kind": "worker"}, 1, NOW, NOW + timedelta(minutes=1)),
            "lease_owned_by_another_owner",
        ),
        (
            ("owner-1", {"kind": "other"}, 1, NOW, NOW + timedelta(minutes=1)),
            "lease_labels_mismatch",
        ),
    ],
)
def test_admission_existing_rejections(row, reason):
    conn = Connection([
        Step("pg_advisory_xact_lock"),
        Step("DELETE FROM tenant_admission_leases WHERE tenant_id = %s AND expires_at <= %s"),
        Step("WHERE tenant_id = %s AND run_id = %s FOR UPDATE", one=row),
        Step("SELECT COUNT(*)", one=(1,)),
    ])
    verdict = admission_backend(conn).admit(request=admission_request(), limit=2)
    assert not verdict.allowed and verdict.reason == reason


@pytest.mark.parametrize(
    ("limit", "active", "reason"),
    [(0, 0, "tenant_runtime_disabled"), (1, 1, "tenant_runtime_capacity_exceeded")],
)
def test_admission_capacity_rejections(limit, active, reason):
    conn = Connection([
        Step("pg_advisory_xact_lock"),
        Step("DELETE FROM tenant_admission_leases WHERE tenant_id = %s AND expires_at <= %s"),
        Step("WHERE tenant_id = %s AND run_id = %s FOR UPDATE", one=None),
        Step("SELECT COUNT(*)", one=(active,)),
    ])
    verdict = admission_backend(conn).admit(request=admission_request(), limit=limit)
    assert not verdict.allowed and verdict.reason == reason


def test_admission_acquire_new_and_token_paths():
    conn = Connection([
        Step("pg_advisory_xact_lock"),
        Step("DELETE FROM tenant_admission_leases WHERE tenant_id = %s AND expires_at <= %s"),
        Step("WHERE tenant_id = %s AND run_id = %s FOR UPDATE", one=None),
        Step("SELECT COUNT(*)", one=None),
        Step("SELECT next_token", one=(6,)),
        Step("INSERT INTO tenant_admission_fencing"),
        Step("INSERT INTO tenant_admission_leases"),
    ])
    verdict = admission_backend(conn).admit(request=admission_request(), limit=2)
    assert verdict.allowed and verdict.reason == "acquired"
    assert verdict.lease.fencing_token == 7


@pytest.mark.parametrize(
    ("row", "exc"),
    [
        (None, KeyError),
        (("other", 1, NOW, NOW + timedelta(minutes=1)), PermissionError),
        (("owner-1", 1, NOW, NOW), KeyError),
    ],
)
def test_admission_renew_locked_failures(row, exc):
    backend = admission_backend()
    cur = Cursor([Step("SELECT owner_id, fencing_token", one=row)])
    with pytest.raises(exc):
        backend._renew_locked(
            cur,
            tenant_id="tenant-a",
            run_id="run-1",
            owner_id="owner-1",
            ttl_seconds=60,
            now=NOW,
        )


def test_admission_renew_release_list_and_decoders():
    renew_conn = Connection([
        Step("pg_advisory_xact_lock"),
        Step("DELETE FROM tenant_admission_leases WHERE tenant_id = %s AND expires_at <= %s"),
        Step(
            "SELECT owner_id, fencing_token",
            one=("owner-1", 2, NOW, datetime(2099, 1, 1, tzinfo=UTC)),
        ),
        Step("UPDATE tenant_admission_leases SET heartbeat_at"),
    ])
    assert admission_backend(renew_conn).renew(
        tenant_id="tenant-a",
        run_id="run-1",
        owner_id="owner-1",
        ttl_seconds=30,
    ).fencing_token == 2

    missing = Connection([
        Step("pg_advisory_xact_lock"),
        Step("DELETE FROM tenant_admission_leases WHERE tenant_id = %s AND expires_at <= %s"),
        Step("SELECT owner_id", one=None),
    ])
    assert admission_backend(missing).release(
        tenant_id="tenant-a",
        run_id="run-1",
        owner_id="owner-1",
    ) is False

    success = Connection([
        Step("pg_advisory_xact_lock"),
        Step("DELETE FROM tenant_admission_leases WHERE tenant_id = %s AND expires_at <= %s"),
        Step("SELECT owner_id", one=("owner-1",)),
        Step("DELETE FROM tenant_admission_leases WHERE tenant_id = %s AND run_id = %s"),
    ])
    assert admission_backend(success).release(
        tenant_id="tenant-a",
        run_id="run-1",
        owner_id="owner-1",
    ) is True

    rows = [("tenant-a", "run-1", "owner-1", 2, NOW, NOW + timedelta(minutes=1))]
    listing = Connection([
        Step("pg_advisory_xact_lock"),
        Step("DELETE FROM tenant_admission_leases WHERE tenant_id = %s AND expires_at <= %s"),
        Step("WHERE tenant_id = %s ORDER BY acquired_at", all=rows),
    ])
    assert len(admission_backend(listing).list_active(tenant_id="tenant-a")) == 1
    assert PostgresTenantAdmissionBackend._decode_labels('{"a":"b"}') == {"a": "b"}
    assert PostgresTenantAdmissionBackend._decode_labels(None) == {}
    with pytest.raises(ValueError, match="labels_json"):
        PostgresTenantAdmissionBackend._decode_labels(["bad"])
    with pytest.raises(ValueError, match="timezone-aware"):
        PostgresTenantAdmissionBackend._ensure_aware(
            datetime(2026, 1, 1),
            field_name="now",
        )

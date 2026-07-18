from __future__ import annotations

import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from billing.scheduler.lease import BillingJobLease
from runtime.platform.billing_scheduler_lease_store import PlatformSqliteBillingJobLeaseStore

NOW=datetime(2099,7,18,tzinfo=UTC)


def _lease(**changes):
    values=dict(tenant_id='tenant-a',job_name='job-a',run_key='run-a',worker_id='worker-a',fencing_token='token-a',acquired_at=NOW,expires_at=NOW+timedelta(seconds=10),metadata={'x':1})
    values.update(changes); return BillingJobLease(**values)


def _store(path: Path, now=NOW): return PlatformSqliteBillingJobLeaseStore(sqlite_path=str(path),lease_cls=BillingJobLease,utc_now_fn=lambda:now)


def test_constructor_schema_and_acquire_replacement(tmp_path: Path) -> None:
    with pytest.raises(ValueError): PlatformSqliteBillingJobLeaseStore(sqlite_path=' ',lease_cls=BillingJobLease,utc_now_fn=lambda:NOW)
    path=tmp_path/'lease.sqlite3'; store=_store(path)
    lease=_lease(); assert store.acquire(lease)==lease
    with pytest.raises(RuntimeError,match='already held'): store.acquire(_lease(fencing_token='other'))
    expired=_lease(fencing_token='new',acquired_at=NOW+timedelta(seconds=11),expires_at=NOW+timedelta(seconds=21))
    assert store.acquire(expired)==expired
    assert store.get(tenant_id='tenant-a',job_name='job-a',run_key='run-a')==expired
    _store(path)
    bad=tmp_path/'bad.sqlite3'; conn=sqlite3.connect(bad); conn.execute('CREATE TABLE billing_schema_version(component TEXT PRIMARY KEY, version INTEGER NOT NULL)'); conn.execute("INSERT INTO billing_schema_version VALUES ('job_leases',999)"); conn.commit(); conn.close()
    with pytest.raises(RuntimeError,match='unsupported'): _store(bad)


def test_get_expiry_validation_and_tenant_isolation(tmp_path: Path) -> None:
    path=tmp_path/'get.sqlite3'; store=_store(path,now=NOW)
    assert store.get(tenant_id='tenant-a',job_name='job',run_key='run') is None
    with pytest.raises(ValueError): store.get(tenant_id='tenant-a',job_name='',run_key='run')
    with pytest.raises(ValueError): store.get(tenant_id='tenant-a',job_name='job',run_key='')
    exp=_lease(acquired_at=NOW-timedelta(seconds=10), expires_at=NOW-timedelta(seconds=1)); store.acquire(exp)
    assert store.get(tenant_id='tenant-a',job_name='job-a',run_key='run-a') is None
    other=_lease(tenant_id='tenant-b',fencing_token='b'); store.acquire(other)
    assert store.get(tenant_id='tenant-a',job_name='job-a',run_key='run-a') is None
    assert store.get(tenant_id='tenant-b',job_name='job-a',run_key='run-a')==other


def test_renew_matrix(tmp_path: Path) -> None:
    store=_store(tmp_path/'renew.sqlite3'); lease=_lease(); store.acquire(lease)
    renewed=store.renew(tenant_id='tenant-a',job_name='job-a',run_key='run-a',fencing_token='token-a',acquired_at=NOW+timedelta(seconds=1),lease_ttl=timedelta(seconds=20))
    assert renewed.expires_at==NOW+timedelta(seconds=21)
    with pytest.raises(ValueError): store.renew(tenant_id='tenant-a',job_name='job',run_key='run',fencing_token='t',acquired_at=datetime(2026,1,1),lease_ttl=timedelta(seconds=1))
    with pytest.raises(ValueError): store.renew(tenant_id='tenant-a',job_name='job',run_key='run',fencing_token='t',acquired_at=NOW,lease_ttl=timedelta(0))
    for job,run,token in [('', 'r','t'),('j','','t'),('j','r','')]:
        with pytest.raises(ValueError): store.renew(tenant_id='tenant-a',job_name=job,run_key=run,fencing_token=token,acquired_at=NOW,lease_ttl=timedelta(seconds=1))
    with pytest.raises(LookupError): store.renew(tenant_id='tenant-a',job_name='missing',run_key='run',fencing_token='t',acquired_at=NOW,lease_ttl=timedelta(seconds=1))
    with pytest.raises(RuntimeError,match='fencing'): store.renew(tenant_id='tenant-a',job_name='job-a',run_key='run-a',fencing_token='wrong',acquired_at=NOW+timedelta(seconds=2),lease_ttl=timedelta(seconds=1))
    expired=_lease(job_name='expired',run_key='run',fencing_token='e',expires_at=NOW+timedelta(seconds=1)); store.acquire(expired)
    with pytest.raises(LookupError): store.renew(tenant_id='tenant-a',job_name='expired',run_key='run',fencing_token='e',acquired_at=NOW+timedelta(seconds=2),lease_ttl=timedelta(seconds=1))


def test_release_matrix(tmp_path: Path) -> None:
    store=_store(tmp_path/'release.sqlite3'); lease=_lease(); store.acquire(lease)
    for job,run,token in [('', 'r','t'),('j','','t'),('j','r','')]:
        with pytest.raises(ValueError): store.release(tenant_id='tenant-a',job_name=job,run_key=run,fencing_token=token)
    assert store.release(tenant_id='tenant-a',job_name='missing',run_key='run',fencing_token='x') is False
    assert store.release(tenant_id='tenant-a',job_name='job-a',run_key='run-a',fencing_token='wrong') is False
    assert store.release(tenant_id='tenant-a',job_name='job-a',run_key='run-a',fencing_token='token-a') is True
    assert store.release(tenant_id='tenant-a',job_name='job-a',run_key='run-a',fencing_token='token-a') is False


def test_encode_decode_and_expiry_none(tmp_path: Path) -> None:
    store=_store(tmp_path/'codec.sqlite3'); lease=_lease(expires_at=None)
    encoded=store._encode(lease); assert encoded['expires_at'] is None
    decoded=store._decode(__import__('json').dumps(encoded)); assert decoded==lease
    assert store._is_expired(lease,now=NOW+timedelta(days=1)) is False


def test_connection_rolls_back_and_closes(tmp_path: Path) -> None:
    store=_store(tmp_path/'rollback.sqlite3')
    with pytest.raises(RuntimeError):
        with store._connect() as conn:
            conn.execute("INSERT INTO billing_schema_version VALUES ('temp',1)")
            raise RuntimeError('stop')
    conn=sqlite3.connect(store._path); assert conn.execute("SELECT * FROM billing_schema_version WHERE component='temp'").fetchone() is None; conn.close()

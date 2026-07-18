from __future__ import annotations

import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

import tenancy.tenant_runtime_lease_store as memory_module
from tenancy.tenant_runtime_lease_sqlite import SQLiteTenantRuntimeLeaseStore, tenancy_runtime_lease_sqlite_path
from tenancy.tenant_runtime_lease_store import (
    InMemoryTenantRuntimeLeaseStore, TenantRuntimeLeaseRecord, ensure_aware, normalize_positive_int, normalize_text,
)

NOW=datetime(2099,7,18,tzinfo=UTC)


def test_helpers_and_record_validation(monkeypatch: pytest.MonkeyPatch) -> None:
    assert ensure_aware(NOW)==NOW
    assert ensure_aware(NOW.astimezone(tz=__import__('datetime').timezone(timedelta(hours=3))) )==NOW
    with pytest.raises(TypeError): ensure_aware('x')
    with pytest.raises(ValueError): ensure_aware(datetime(2026,1,1))
    assert normalize_positive_int('2',field_name='x')==2
    with pytest.raises(ValueError): normalize_positive_int(0,field_name='x')
    assert normalize_text(' x ',field_name='x')=='x'
    with pytest.raises(ValueError): normalize_text(' ',field_name='x')
    assert memory_module.utc_now().tzinfo is not None
    record=TenantRuntimeLeaseRecord('tenant-a','run','owner','slot',1,NOW,NOW,NOW+timedelta(seconds=1),{'k':'v'})
    record.validate(); assert record.fencing.value==1
    monkeypatch.setattr(memory_module,'utc_now',lambda:NOW+timedelta(seconds=2)); assert record.expired
    bads=[
        dict(fencing_token=0),dict(heartbeat_at=NOW-timedelta(seconds=1)),dict(expires_at=NOW),dict(labels={'':'v'}),dict(labels={'k':''})
    ]
    for changes in bads:
        vals=record.__dict__|changes
        with pytest.raises(ValueError): TenantRuntimeLeaseRecord(**vals).validate()


def _exercise_store(store, *, monkeypatch=None):
    first=store.acquire(tenant_id='tenant-a',run_id='run-a',owner_id='owner-a',limit=2,ttl_seconds=10,labels={'role':'worker'},now=NOW)
    assert first.allowed and first.reason=='acquired' and first.active_runs==1 and first.lease.fencing_token==1
    same=store.acquire(tenant_id='tenant-a',run_id='run-a',owner_id='owner-a',limit=2,ttl_seconds=20,labels={'role':'worker'},now=NOW+timedelta(seconds=1))
    assert same.allowed and same.reason=='already_acquired' and same.lease.fencing_token==1
    assert not store.acquire(tenant_id='tenant-a',run_id='run-a',owner_id='other',limit=2,ttl_seconds=10,labels={'role':'worker'},now=NOW+timedelta(seconds=2)).allowed
    assert store.acquire(tenant_id='tenant-a',run_id='run-a',owner_id='owner-a',limit=2,ttl_seconds=10,labels={'role':'other'},now=NOW+timedelta(seconds=2)).reason=='lease_labels_mismatch'
    second=store.acquire(tenant_id='tenant-a',run_id='run-b',owner_id='owner-b',limit=2,ttl_seconds=10,now=NOW)
    assert second.lease.fencing_token==2
    assert store.acquire(tenant_id='tenant-a',run_id='run-c',owner_id='owner-c',limit=2,ttl_seconds=10,now=NOW).reason=='tenant_runtime_capacity_exceeded'
    assert store.acquire(tenant_id='tenant-b',run_id='disabled',owner_id='owner',limit=0,ttl_seconds=10,now=NOW).reason=='tenant_runtime_disabled'
    renewed=store.renew(tenant_id='tenant-a',run_id='run-a',owner_id='owner-a',ttl_seconds=30,now=NOW+timedelta(seconds=3)); assert renewed.heartbeat_at==NOW+timedelta(seconds=3)
    with pytest.raises(PermissionError): store.renew(tenant_id='tenant-a',run_id='run-a',owner_id='bad',ttl_seconds=10,now=NOW)
    with pytest.raises(KeyError): store.renew(tenant_id='tenant-a',run_id='missing',owner_id='owner',ttl_seconds=10,now=NOW)
    assert store.get(tenant_id='tenant-a',run_id='run-a') is not None
    assert store.get(tenant_id='tenant-a',run_id='missing') is None
    active=store.list_active(tenant_id='tenant-a',now=NOW); assert [x.run_id for x in active]==['run-a','run-b']
    assert store.release(tenant_id='tenant-a',run_id='missing',owner_id='owner') is False
    with pytest.raises(PermissionError): store.release(tenant_id='tenant-a',run_id='run-a',owner_id='bad')
    assert store.release(tenant_id='tenant-a',run_id='run-a',owner_id='owner-a') is True
    expired=store.reap_expired(now=NOW+timedelta(seconds=20)); assert [x.run_id for x in expired]==['run-b']


def test_in_memory_store_complete_contract(monkeypatch: pytest.MonkeyPatch) -> None:
    store=InMemoryTenantRuntimeLeaseStore(); _exercise_store(store)
    exp=store.acquire(tenant_id='tenant-a',run_id='exp',owner_id='o',limit=1,ttl_seconds=1,now=NOW).lease
    monkeypatch.setattr(memory_module,'utc_now',lambda:NOW+timedelta(seconds=2))
    assert store.get(tenant_id='tenant-a',run_id='exp') is None
    assert store._active_count_locked(tenant_id='tenant-a')==0
    assert store._next_token_locked(tenant_id='tenant-a')>=2


def test_sqlite_store_complete_contract_and_connection_closure(tmp_path: Path) -> None:
    store=SQLiteTenantRuntimeLeaseStore(tmp_path/'leases.sqlite3'); assert store.path.name=='leases.sqlite3'
    _exercise_store(store)
    assert store.schema_version()==1
    assert store.read_backend_clock().tzinfo is not None
    assert store._ts(NOW)==NOW.isoformat(); assert store._ts(NOW,ttl_seconds=1)==(NOW+timedelta(seconds=1)).isoformat()
    assert store._encode_labels({' b ':' 2 ','a':'1'})=='{"a":"1","b":"2"}'
    with pytest.raises(ValueError): store._encode_labels({'':'x'})
    with store._connect(write=False) as conn:
        assert store._active_count_locked(conn,tenant_id='missing')==0
    with pytest.raises(RuntimeError):
        with store._connect(write=True) as conn:
            conn.execute("INSERT INTO tenant_runtime_lease_tokens VALUES ('temp',1)")
            raise RuntimeError('stop')
    conn=sqlite3.connect(store.path); assert conn.execute("SELECT * FROM tenant_runtime_lease_tokens WHERE tenant_id='temp'").fetchone() is None; conn.close()


def test_sqlite_path_resolution(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv('BUSINESAIOS_TENANT_RUNTIME_LEASE_SQLITE_PATH',str(tmp_path/'explicit.db'))
    assert tenancy_runtime_lease_sqlite_path()==tmp_path/'explicit.db'
    monkeypatch.delenv('BUSINESAIOS_TENANT_RUNTIME_LEASE_SQLITE_PATH')
    monkeypatch.setenv('BUSINESAIOS_TENANCY_DATA_DIR',str(tmp_path/'tenancy'))
    assert tenancy_runtime_lease_sqlite_path()==tmp_path/'tenancy'/'tenant_runtime_leases.sqlite3'
    monkeypatch.delenv('BUSINESAIOS_TENANCY_DATA_DIR'); monkeypatch.setenv('DATA_DIR',' ')
    assert tenancy_runtime_lease_sqlite_path()==Path('data/tenancy/tenant_runtime_leases.sqlite3')


def test_sqlite_lost_insert_and_renew_branches(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    store=SQLiteTenantRuntimeLeaseStore(tmp_path/'fake.db')
    class Cursor:
        def __init__(self,one=None,all_rows=()): self.one=one; self.all_rows=all_rows
        def fetchone(self): return self.one
        def fetchall(self): return self.all_rows
    class Conn:
        def execute(self,sql,params=()):
            if sql.startswith('SELECT COUNT'): return Cursor((0,))
            if sql.startswith('SELECT next_token'): return Cursor(None)
            if 'FROM tenant_runtime_leases WHERE tenant_id = ? AND run_id = ?' in sql: return Cursor(None)
            if 'WHERE expires_at <=' in sql: return Cursor(all_rows=())
            return Cursor()
    from contextlib import contextmanager
    @contextmanager
    def fake_connect(**kwargs): yield Conn()
    monkeypatch.setattr(store,'_connect',fake_connect)
    with pytest.raises(RuntimeError,match='insert did not persist'):
        store.acquire(tenant_id='tenant-a',run_id='run',owner_id='owner',limit=1,ttl_seconds=1,now=NOW)
    current=TenantRuntimeLeaseRecord('tenant-a','run','owner','slot',1,NOW,NOW,NOW+timedelta(seconds=1),{})
    with pytest.raises(RuntimeError,match='renew lost record'):
        store._renew_locked(Conn(),current=current,ttl_seconds=1,now=NOW)

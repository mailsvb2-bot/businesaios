from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from billing.dispute_orchestrator import DisputeCase, DisputeOrchestrator, InMemoryDisputeStore, SqliteDisputeStore
from billing.dispute_policy import DisputeClassification, DisputePolicy
from runtime.platform.billing_dispute_store import PlatformSqliteDisputeStore

NOW=datetime(2026,7,18,tzinfo=UTC); FP="fingerprint"


def _classification(**changes):
    values=dict(case_type="general_review",severity="low",metadata={"owner":"test"}); values.update(changes); return DisputeClassification(**values)


def _case(**changes):
    values=dict(tenant_id="tenant-a",invoice_id="invoice-a",case_id="case-a",classification=_classification(),status="open",idempotency_key="key-a",opened_at=NOW,resolved_at=None,resolution=None,metadata={"evidence_fingerprint":FP}); values.update(changes); return DisputeCase(**values)


class _Metrics:
    def __init__(self): self.calls=[]
    def inc(self,**kwargs): self.calls.append(kwargs)


def test_dispute_case_validation_matrix() -> None:
    case=_case(); case.validate()
    for name,value in {"tenant_id":"","invoice_id":"","case_id":"","status":"unknown","opened_at":datetime(2026,1,1),"idempotency_key":" ","metadata":{}}.items():
        with pytest.raises(ValueError): replace(case,**{name:value}).validate()
    with pytest.raises(ValueError): replace(case,classification=_classification(case_type="")).validate()
    with pytest.raises(ValueError): replace(case,classification=_classification(severity="critical")).validate()
    with pytest.raises(ValueError): replace(case,status="resolved",resolution=None,resolved_at=NOW).validate()
    with pytest.raises(ValueError): replace(case,status="open",resolved_at=NOW).validate()
    with pytest.raises(ValueError): replace(case,status="resolved",resolution="done",resolved_at=datetime(2026,1,1)).validate()
    replace(case,status="resolved",resolution="done",resolved_at=NOW).validate()


def test_dispute_policy_classifies_all_cases() -> None:
    policy=DisputePolicy()
    for payload,case_type,severity in [
        ({"attribution_mismatch":True,"duplicate_flag":True},"compound_attribution_duplicate_challenge","high"),
        ({"missing_proof":True},"evidence_gap_review","medium"),({"existing_customer_flag":True},"existing_customer_challenge","medium"),
        ({"duplicate_flag":True},"duplicate_lead_challenge","medium"),({"attribution_mismatch":True},"attribution_challenge","high"),({},"general_review","low")]:
        result=policy.classify(payload); assert (result.case_type,result.severity)==(case_type,severity)


def test_in_memory_store_allows_same_case_lifecycle_update_with_idempotency() -> None:
    store=InMemoryDisputeStore(); case=_case(); assert store.save(case,idempotency_key=" key-a ")==case; assert store.save(case,idempotency_key="key-a")==case
    resolved=replace(case,status="resolved",resolution="won",resolved_at=NOW+timedelta(seconds=1)); assert store.save(resolved,idempotency_key="key-a")==resolved
    assert store.get_by_idempotency(tenant_id="tenant-a",invoice_id="invoice-a",idempotency_key="key-a")==resolved
    assert store.get(tenant_id="tenant-a",case_id="case-a")==resolved
    with pytest.raises(ValueError,match="idempotency"): store.save(replace(case,case_id="other"),idempotency_key="key-a")
    with pytest.raises(ValueError,match="case_id collision"): store.save(replace(case,invoice_id="invoice-b",idempotency_key=None))
    blank1=replace(case,case_id="blank-1",idempotency_key=None,opened_at=NOW+timedelta(seconds=2)); blank2=replace(case,case_id="blank-2",idempotency_key=None,opened_at=NOW+timedelta(seconds=3))
    store.save(blank1,idempotency_key=" "); store.save(blank2,idempotency_key=" ")
    assert [x.case_id for x in store.list_for_invoice(tenant_id="tenant-a",invoice_id="invoice-a")]==["case-a","blank-1","blank-2"]
    assert store.get(tenant_id="tenant-b",case_id="case-a") is None


def test_orchestrator_open_replay_fingerprint_metrics_and_blank_key() -> None:
    metrics=_Metrics(); store=InMemoryDisputeStore(); orch=DisputeOrchestrator(store=store,metrics=metrics); payload={"missing_proof":True,"when":NOW}
    opened=orch.open_case(tenant_id="tenant-a",invoice_id=" invoice-a ",payload=payload,idempotency_key=" key-a ",opened_at=NOW,metadata={"source":"test"})
    assert opened.classification.case_type=="evidence_gap_review" and opened.idempotency_key=="key-a"
    assert orch.open_case(tenant_id="tenant-a",invoice_id="invoice-a",payload=payload,idempotency_key="key-a",opened_at=NOW)==opened
    with pytest.raises(ValueError,match="fingerprint mismatch"): orch.open_case(tenant_id="tenant-a",invoice_id="invoice-a",payload={"missing_proof":False},idempotency_key="key-a")
    blank=orch.open_case(tenant_id="tenant-a",invoice_id="invoice-a",payload={},idempotency_key=" ",opened_at=NOW); assert blank.idempotency_key is None
    with pytest.raises(ValueError,match="invoice_id"): orch.open_case(tenant_id="tenant-a",invoice_id=" ",payload={})
    with pytest.raises(ValueError,match="opened_at"): orch.open_case(tenant_id="tenant-a",invoice_id="invoice-a",payload={},opened_at=datetime(2026,1,1))
    assert orch._payload_fingerprint({"b":2,"a":1})==orch._payload_fingerprint({"a":1,"b":2}) and len(orch._payload_fingerprint({"at":NOW}))==64


def test_orchestrator_resolve_reject_escalate_and_fail_closed() -> None:
    metrics=_Metrics(); store=InMemoryDisputeStore(); orch=DisputeOrchestrator(store=store,metrics=metrics)
    case=orch.open_case(tenant_id="tenant-a",invoice_id="invoice-a",payload={},idempotency_key="key",opened_at=NOW)
    resolved=orch.resolve_case(case=case,resolution=" accepted ",resolved_at=NOW+timedelta(seconds=1),metadata={"agent":"a"})
    assert resolved.status=="resolved" and store.get_by_idempotency(tenant_id="tenant-a",invoice_id="invoice-a",idempotency_key="key")==resolved
    with pytest.raises(ValueError,match="only open"): orch.resolve_case(case=resolved,resolution="again")
    with pytest.raises(ValueError,match="resolution status"): orch.resolve_case(case=case,resolution="x",status="unknown")
    with pytest.raises(ValueError,match="resolution is required"): orch.resolve_case(case=case,resolution=" ")
    with pytest.raises(ValueError,match="resolved_at"): orch.resolve_case(case=case,resolution="x",resolved_at=datetime(2026,1,1))
    rejected=orch.reject_case(case=orch.open_case(tenant_id="tenant-a",invoice_id="invoice-b",payload={},opened_at=NOW),resolution="no",resolved_at=NOW)
    escalated=orch.escalate_case(case=orch.open_case(tenant_id="tenant-a",invoice_id="invoice-c",payload={},opened_at=NOW),resolution="manual",resolved_at=NOW)
    assert rejected.status=="rejected" and escalated.status=="escalated"


def _seed_schema(path:Path,version:int):
    conn=sqlite3.connect(path); conn.execute('CREATE TABLE billing_schema_version(component TEXT PRIMARY KEY,version INTEGER NOT NULL)'); conn.execute("INSERT INTO billing_schema_version VALUES ('dispute_store',?)",(version,)); conn.commit(); conn.close()


def test_sqlite_store_insert_update_queries_blank_key_and_schema(tmp_path:Path) -> None:
    with pytest.raises(ValueError): PlatformSqliteDisputeStore(sqlite_path=" ",case_cls=DisputeCase)
    bad=tmp_path/'bad.sqlite3'; _seed_schema(bad,999)
    with pytest.raises(RuntimeError,match="unsupported"): PlatformSqliteDisputeStore(sqlite_path=str(bad),case_cls=DisputeCase)
    path=tmp_path/'disputes.sqlite3'; store=SqliteDisputeStore(sqlite_path=str(path)); SqliteDisputeStore(sqlite_path=str(path))
    case=_case(); assert store.save(case,idempotency_key="key-a")==case
    updated=replace(case,status="resolved",resolution="done",resolved_at=NOW+timedelta(seconds=1)); assert store.save(updated,idempotency_key="key-a")==updated
    assert store.list_for_invoice(tenant_id="tenant-a",invoice_id="invoice-a")== (updated,)
    blank1=replace(case,case_id="blank-1",idempotency_key=None,opened_at=NOW+timedelta(seconds=2)); blank2=replace(case,case_id="blank-2",idempotency_key=None,opened_at=NOW+timedelta(seconds=3))
    store.save(blank1,idempotency_key=" "); store.save(blank2,idempotency_key=" ")
    assert store.get(tenant_id="tenant-b",case_id="case-a") is None and store.get_by_idempotency(tenant_id="tenant-a",invoice_id="invoice-a",idempotency_key="missing") is None
    with pytest.raises(ValueError): store.get_by_idempotency(tenant_id="tenant-a",invoice_id="",idempotency_key="x")
    with pytest.raises(ValueError): store.get_by_idempotency(tenant_id="tenant-a",invoice_id="i",idempotency_key=" ")
    with pytest.raises(ValueError): store.get(tenant_id="tenant-a",case_id=" ")
    with pytest.raises(ValueError): store.list_for_invoice(tenant_id="tenant-a",invoice_id=" ")
    with pytest.raises(ValueError,match="case_id collision"): store.save(replace(case,invoice_id="invoice-b",idempotency_key=None))


def test_sqlite_store_integrity_race_matrix_and_codec(tmp_path:Path,monkeypatch:pytest.MonkeyPatch) -> None:
    store=PlatformSqliteDisputeStore(sqlite_path=str(tmp_path/'race.sqlite3'),case_cls=DisputeCase); case=_case(); assert store._decode(json.dumps(store._encode(case)))==case
    class Cursor:
        def fetchone(self): return None
    class Conn:
        def execute(self,sql,params=()):
            if sql.startswith('SELECT payload_json'): return Cursor()
            raise sqlite3.IntegrityError('race')
    @contextmanager
    def connect(): yield Conn()
    monkeypatch.setattr(store,'_connect',connect); monkeypatch.setattr(store,'get_by_idempotency',lambda **kwargs: case); assert store.save(case,idempotency_key="key-a")==case
    monkeypatch.setattr(store,'get_by_idempotency',lambda **kwargs: replace(case,case_id="other"))
    with pytest.raises(ValueError,match="idempotency"): store.save(case,idempotency_key="key-a")
    monkeypatch.setattr(store,'get_by_idempotency',lambda **kwargs: None); monkeypatch.setattr(store,'get',lambda **kwargs: None)
    with pytest.raises(sqlite3.IntegrityError): store.save(case)
    monkeypatch.setattr(store,'get',lambda **kwargs: case); assert store.save(case)==case
    monkeypatch.setattr(store,'get',lambda **kwargs: replace(case,status="resolved",resolution="x",resolved_at=NOW))
    with pytest.raises(ValueError,match="case collision"): store.save(case)


def test_sqlite_connection_rolls_back_and_closes(tmp_path:Path) -> None:
    store=PlatformSqliteDisputeStore(sqlite_path=str(tmp_path/'rollback.sqlite3'),case_cls=DisputeCase)
    with pytest.raises(RuntimeError):
        with store._connect() as conn:
            conn.execute("INSERT INTO billing_schema_version VALUES ('temp',1)"); raise RuntimeError('stop')
    conn=sqlite3.connect(store._path); assert conn.execute("SELECT * FROM billing_schema_version WHERE component='temp'").fetchone() is None; conn.close()


def test_orchestrator_without_metrics_covers_noop_observability_branches() -> None:
    orch=DisputeOrchestrator(); case=orch.open_case(tenant_id='tenant-a',invoice_id='invoice-a',payload={},opened_at=NOW); assert orch.resolve_case(case=case,resolution='done',resolved_at=NOW).status=='resolved'


def test_sqlite_idempotency_integrity_falls_through_when_lookup_missing(tmp_path:Path,monkeypatch:pytest.MonkeyPatch) -> None:
    store=PlatformSqliteDisputeStore(sqlite_path=str(tmp_path/'idem-fallthrough.sqlite3'),case_cls=DisputeCase); case=_case()
    class Cursor:
        def fetchone(self): return None
    class Conn:
        def execute(self,sql,params=()):
            if sql.startswith('SELECT payload_json'): return Cursor()
            raise sqlite3.IntegrityError('race')
    @contextmanager
    def connect(): yield Conn()
    monkeypatch.setattr(store,'_connect',connect); monkeypatch.setattr(store,'get_by_idempotency',lambda **kwargs: None); monkeypatch.setattr(store,'get',lambda **kwargs: case)
    assert store.save(case,idempotency_key='key-a')==case

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from billing.commercial_cycle_contract import CommercialCollectionResult
from billing.ledger_event import LedgerEntry, LedgerPosting
from billing.recovery_contracts import ChargebackCase, RefundResult
from runtime.platform.billing_recovery_store import PlatformSqliteChargebackStore, PlatformSqliteRefundStore
from runtime.platform.billing_sqlite_store import PlatformSqliteCollectionResultStore, PlatformSqliteLedgerStore

NOW = datetime(2026, 7, 18, tzinfo=UTC)


def _refund(**changes):
    values = dict(tenant_id='tenant-a', invoice_id='invoice-a', refund_id='refund-a', amount_minor=100,
                  currency='USD', provider_name='provider', external_reference='ext', processed_at=NOW,
                  metadata={'source': 'test'})
    values.update(changes)
    return RefundResult(**values)


def _case(**changes):
    values = dict(tenant_id='tenant-a', invoice_id='invoice-a', user_id='user-a', amount_minor=100,
                  currency='USD', reason='fraud', opened_at=NOW, case_id='case-a',
                  idempotency_key='business-key', metadata={'source': 'test'})
    values.update(changes)
    return ChargebackCase(**values)


def _collection(**changes):
    values = dict(invoice_id='invoice-a', tenant_id='tenant-a', provider_name='provider', successful=True,
                  external_reference='ext', failure_reason=None, retryable=False, processed_at=NOW,
                  metadata={'source': 'test'})
    values.update(changes)
    return CommercialCollectionResult(**values)


def _entry(entry_id: str, side: str, account: str, *, amount=100, tenant='tenant-a', booked_at=NOW):
    return LedgerEntry(tenant_id=tenant, entry_id=entry_id, account_code=account, side=side,
                       amount_minor=amount, currency='USD', reference_type='invoice', reference_id='invoice-a',
                       booked_at=booked_at, metadata={'x': 1})


def _posting(**changes):
    values = dict(posting_id='posting-a', tenant_id='tenant-a', reference_type='invoice', reference_id='invoice-a',
                  entries=(_entry('debit-a', 'debit', 'cash'), _entry('credit-a', 'credit', 'revenue')),
                  metadata={'source': 'test'})
    values.update(changes)
    return LedgerPosting(**values)


def _seed_schema(path: Path, component: str, version: int) -> None:
    conn = sqlite3.connect(path)
    conn.execute('CREATE TABLE billing_schema_version(component TEXT PRIMARY KEY, version INTEGER NOT NULL)')
    conn.execute('INSERT INTO billing_schema_version VALUES (?, ?)', (component, version))
    conn.commit(); conn.close()


def test_constructor_validation_and_schema_version_fail_closed(tmp_path: Path) -> None:
    with pytest.raises(ValueError): PlatformSqliteRefundStore(sqlite_path=' ', result_cls=RefundResult)
    with pytest.raises(ValueError): PlatformSqliteChargebackStore(sqlite_path='', case_cls=ChargebackCase)
    with pytest.raises(ValueError): PlatformSqliteCollectionResultStore(sqlite_path=' ')
    with pytest.raises(ValueError): PlatformSqliteLedgerStore(sqlite_path='')
    for cls, component, kwargs in [
        (PlatformSqliteRefundStore, 'refund_results', {'result_cls': RefundResult}),
        (PlatformSqliteChargebackStore, 'chargeback_cases', {'case_cls': ChargebackCase}),
        (PlatformSqliteCollectionResultStore, 'collection_results', {}),
        (PlatformSqliteLedgerStore, 'ledger_postings', {}),
    ]:
        path = tmp_path / f'{component}.sqlite3'
        _seed_schema(path, component, 999)
        with pytest.raises(RuntimeError, match='unsupported'):
            cls(sqlite_path=str(path), **kwargs)


def test_refund_store_replay_collision_blank_key_and_tenant_isolation(tmp_path: Path) -> None:
    store = PlatformSqliteRefundStore(sqlite_path=str(tmp_path/'refund.sqlite3'), result_cls=RefundResult)
    result = _refund()
    assert store.save(result, idempotency_key='key-a') == result
    assert store.save(result, idempotency_key='key-a') == result
    assert store.save(result) == result
    assert store.get_by_idempotency(tenant_id='tenant-a', invoice_id='invoice-a', idempotency_key='key-a') == result
    assert store.get_by_idempotency(tenant_id='tenant-b', invoice_id='invoice-a', idempotency_key='key-a') is None
    assert store.list_for_invoice(tenant_id='tenant-a', invoice_id='invoice-a') == (result,)
    assert store.list_for_invoice(tenant_id='tenant-b', invoice_id='invoice-a') == ()
    with pytest.raises(ValueError): store.get_by_idempotency(tenant_id='tenant-a', invoice_id='', idempotency_key='x')
    with pytest.raises(ValueError): store.get_by_idempotency(tenant_id='tenant-a', invoice_id='i', idempotency_key=' ')
    with pytest.raises(ValueError): store.list_for_invoice(tenant_id='tenant-a', invoice_id=' ')
    with pytest.raises(ValueError, match='idempotency_key collision'):
        store.save(_refund(refund_id='refund-b', amount_minor=101), idempotency_key='key-a')
    with pytest.raises(ValueError, match='refund_id collision'):
        store.save(_refund(amount_minor=101))
    blank_one = _refund(refund_id='refund-blank-1', processed_at=NOW+timedelta(seconds=1))
    blank_two = _refund(refund_id='refund-blank-2', processed_at=NOW+timedelta(seconds=2))
    assert store.save(blank_one, idempotency_key=' ') == blank_one
    assert store.save(blank_two, idempotency_key=' ') == blank_two
    assert store._decode_result_payload(__import__('json').dumps({
        'tenant_id':'tenant-a','invoice_id':'invoice-a','refund_id':'decoded','amount_minor':1,'currency':'USD',
        'provider_name':'p','external_reference':'e','processed_at':NOW.isoformat(),'metadata':{}
    })).refund_id == 'decoded'


def test_chargeback_store_preserves_business_idempotency_and_replays_external_key(tmp_path: Path) -> None:
    store = PlatformSqliteChargebackStore(sqlite_path=str(tmp_path/'charge.sqlite3'), case_cls=ChargebackCase)
    case = _case()
    assert store.save(case, idempotency_key='transport-key') == case
    assert store.get_by_idempotency(tenant_id='tenant-a', invoice_id='invoice-a', idempotency_key='transport-key') == case
    assert store.save(case, idempotency_key='transport-key') == case
    assert store.save(case) == case
    with pytest.raises(ValueError, match='idempotency'):
        store.save(_case(case_id='case-b', amount_minor=101), idempotency_key='transport-key')
    with pytest.raises(ValueError, match='case collision'):
        store.save(_case(amount_minor=101))
    assert store.list_for_invoice(tenant_id='tenant-a', invoice_id='invoice-a') == (case,)
    assert store.list_for_invoice(tenant_id='tenant-b', invoice_id='invoice-a') == ()
    with pytest.raises(ValueError): store.get_by_idempotency(tenant_id='tenant-a', invoice_id='', idempotency_key='x')
    with pytest.raises(ValueError): store.get_by_idempotency(tenant_id='tenant-a', invoice_id='i', idempotency_key='')
    with pytest.raises(ValueError): store.list_for_invoice(tenant_id='tenant-a', invoice_id='')
    blank1 = _case(case_id='blank-1', idempotency_key=None, opened_at=NOW+timedelta(seconds=1))
    blank2 = _case(case_id='blank-2', idempotency_key=None, opened_at=NOW+timedelta(seconds=2))
    assert store.save(blank1, idempotency_key=' ') == blank1
    assert store.save(blank2, idempotency_key=' ') == blank2


def test_collection_store_replay_collisions_global_and_tenant_listing(tmp_path: Path) -> None:
    store = PlatformSqliteCollectionResultStore(sqlite_path=str(tmp_path/'collection.sqlite3'))
    result = _collection()
    assert store.append(result, idempotency_key='key-a') == result
    assert store.append(result, idempotency_key='key-a') == result
    with pytest.raises(ValueError, match='idempotency_key collision'):
        store.append(_collection(processed_at=NOW+timedelta(seconds=1), external_reference='other'), idempotency_key='key-a')
    same_pk = _collection(metadata={'source':'test'})
    assert store.append(same_pk) == result
    with pytest.raises(ValueError, match='primary key collision'):
        store.append(_collection(external_reference='different'))
    tenant_b = _collection(tenant_id='tenant-b', external_reference='b')
    assert store.append(tenant_b, idempotency_key='key-a') == tenant_b
    assert len(store.list_for_invoice('invoice-a')) == 2
    assert store.list_for_invoice('invoice-a', tenant_id='tenant-a') == (result,)
    assert store.get_by_idempotency(tenant_id='tenant-b', invoice_id='invoice-a', idempotency_key='key-a') == tenant_b
    assert store.get_by_idempotency(tenant_id='tenant-a', invoice_id='missing', idempotency_key='key-a') is None
    with pytest.raises(ValueError): store.get_by_idempotency(tenant_id='tenant-a', invoice_id='', idempotency_key='x')
    with pytest.raises(ValueError): store.get_by_idempotency(tenant_id='tenant-a', invoice_id='i', idempotency_key='')
    with pytest.raises(ValueError): store.list_for_invoice(' ')
    blank1 = _collection(invoice_id='blank', processed_at=NOW+timedelta(seconds=1), external_reference='1')
    blank2 = _collection(invoice_id='blank', processed_at=NOW+timedelta(seconds=2), external_reference='2')
    assert store.append(blank1, idempotency_key=' ') == blank1
    assert store.append(blank2, idempotency_key=' ') == blank2


def test_ledger_store_roundtrip_collision_totals_and_tenant_isolation(tmp_path: Path) -> None:
    store = PlatformSqliteLedgerStore(sqlite_path=str(tmp_path/'ledger.sqlite3'))
    posting = _posting()
    assert store.append(posting) == posting
    assert store.append(posting) == posting
    with pytest.raises(ValueError, match='posting_id collision'):
        store.append(_posting(entries=(_entry('d2','debit','cash',amount=101), _entry('c2','credit','revenue',amount=101))))
    tenant_b = _posting(tenant_id='tenant-b', entries=(_entry('bd','debit','cash',tenant='tenant-b'), _entry('bc','credit','revenue',tenant='tenant-b')))
    assert store.append(tenant_b) == tenant_b
    assert store.list_postings(tenant_id='tenant-a') == (posting,)
    assert store.list_postings(tenant_id='tenant-b') == (tenant_b,)
    assert store.total_for_account(tenant_id='tenant-a', account_code='cash') == 100
    assert store.total_for_account(tenant_id='tenant-a', account_code='cash', side='debit') == 100
    assert store.total_for_account(tenant_id='tenant-a', account_code='cash', side='credit') == 0
    assert store.total_for_account(tenant_id='tenant-a', account_code='missing') == 0
    with pytest.raises(ValueError): store.total_for_account(tenant_id='tenant-a', account_code=' ')
    with pytest.raises(ValueError): store.total_for_account(tenant_id='tenant-a', account_code='cash', side='other')


def test_integrity_error_fallback_paths_are_fail_closed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    refund_store = PlatformSqliteRefundStore(sqlite_path=str(tmp_path/'r.sqlite3'), result_cls=RefundResult)
    charge_store = PlatformSqliteChargebackStore(sqlite_path=str(tmp_path/'c.sqlite3'), case_cls=ChargebackCase)
    ledger_store = PlatformSqliteLedgerStore(sqlite_path=str(tmp_path/'l.sqlite3'))
    refund = _refund(); case = _case(); posting = _posting()
    refund_store.save(refund, idempotency_key='rk')
    charge_store.save(case, idempotency_key='ck')
    ledger_store.append(posting)
    assert refund_store.save(refund, idempotency_key='rk') == refund
    assert charge_store.save(case, idempotency_key='ck') == case
    assert ledger_store.append(posting) == posting


def test_connection_context_rolls_back_on_error_and_closes(tmp_path: Path) -> None:
    store = PlatformSqliteRefundStore(sqlite_path=str(tmp_path/'rollback.sqlite3'), result_cls=RefundResult)
    with pytest.raises(RuntimeError):
        with store._connect() as conn:
            conn.execute("INSERT INTO billing_schema_version(component, version) VALUES ('temporary',1)")
            raise RuntimeError('stop')
    conn = sqlite3.connect(store._path)
    assert conn.execute("SELECT version FROM billing_schema_version WHERE component='temporary'").fetchone() is None
    conn.close()


def test_existing_schema_versions_are_accepted(tmp_path: Path) -> None:
    path = tmp_path/'shared.sqlite3'
    PlatformSqliteRefundStore(sqlite_path=str(path), result_cls=RefundResult)
    PlatformSqliteRefundStore(sqlite_path=str(path), result_cls=RefundResult)
    PlatformSqliteChargebackStore(sqlite_path=str(path), case_cls=ChargebackCase)
    PlatformSqliteChargebackStore(sqlite_path=str(path), case_cls=ChargebackCase)
    PlatformSqliteCollectionResultStore(sqlite_path=str(path))
    PlatformSqliteCollectionResultStore(sqlite_path=str(path))
    PlatformSqliteLedgerStore(sqlite_path=str(path))
    PlatformSqliteLedgerStore(sqlite_path=str(path))


def test_refund_integrity_race_resolution_matrix(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from contextlib import contextmanager
    store = PlatformSqliteRefundStore(sqlite_path=str(tmp_path/'refund-race.sqlite3'), result_cls=RefundResult)
    result = _refund()
    class Conn:
        def execute(self, sql, params=()):
            if sql.startswith('SELECT payload_json'):
                return SimpleCursor(None)
            raise sqlite3.IntegrityError('race')
    class SimpleCursor:
        def __init__(self, row): self.row=row
        def fetchone(self): return self.row
    @contextmanager
    def connect(): yield Conn()
    monkeypatch.setattr(store, '_connect', connect)
    monkeypatch.setattr(store, 'get_by_idempotency', lambda **kwargs: result)
    assert store.save(result, idempotency_key='k') == result
    monkeypatch.setattr(store, 'get_by_idempotency', lambda **kwargs: _refund(amount_minor=101))
    with pytest.raises(ValueError, match='idempotency_key collision'):
        store.save(result, idempotency_key='k')
    monkeypatch.setattr(store, 'get_by_idempotency', lambda **kwargs: None)
    monkeypatch.setattr(store, 'list_for_invoice', lambda **kwargs: ())
    with pytest.raises(sqlite3.IntegrityError): store.save(result)
    monkeypatch.setattr(store, 'list_for_invoice', lambda **kwargs: (result,))
    assert store.save(result) == result
    monkeypatch.setattr(store, 'list_for_invoice', lambda **kwargs: (_refund(amount_minor=101),))
    with pytest.raises(ValueError, match='refund_id collision'): store.save(result)


def test_chargeback_integrity_race_resolution_matrix(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from contextlib import contextmanager
    store = PlatformSqliteChargebackStore(sqlite_path=str(tmp_path/'case-race.sqlite3'), case_cls=ChargebackCase)
    case = _case()
    class Cursor:
        def fetchone(self): return None
    class Conn:
        def execute(self, sql, params=()):
            if sql.startswith('SELECT payload_json'): return Cursor()
            raise sqlite3.IntegrityError('race')
    @contextmanager
    def connect(): yield Conn()
    monkeypatch.setattr(store, '_connect', connect)
    monkeypatch.setattr(store, 'get_by_idempotency', lambda **kwargs: case)
    assert store.save(case, idempotency_key='k') == case
    monkeypatch.setattr(store, 'get_by_idempotency', lambda **kwargs: _case(amount_minor=101))
    with pytest.raises(ValueError, match='idempotency'): store.save(case, idempotency_key='k')
    monkeypatch.setattr(store, 'get_by_idempotency', lambda **kwargs: None)
    monkeypatch.setattr(store, 'list_for_invoice', lambda **kwargs: ())
    with pytest.raises(sqlite3.IntegrityError): store.save(case)
    monkeypatch.setattr(store, 'list_for_invoice', lambda **kwargs: (case,))
    assert store.save(case) == case
    monkeypatch.setattr(store, 'list_for_invoice', lambda **kwargs: (_case(amount_minor=101),))
    with pytest.raises(ValueError, match='case collision'): store.save(case)


def test_collection_integrity_race_resolution_matrix(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from contextlib import contextmanager
    store = PlatformSqliteCollectionResultStore(sqlite_path=str(tmp_path/'collection-race.sqlite3'))
    result = _collection()
    class Conn:
        def execute(self, *args, **kwargs): raise sqlite3.IntegrityError('race')
    @contextmanager
    def connect(): yield Conn()
    monkeypatch.setattr(store, '_connect', connect)
    monkeypatch.setattr(store, 'get_by_idempotency', lambda **kwargs: result)
    assert store.append(result, idempotency_key='k') == result
    monkeypatch.setattr(store, 'get_by_idempotency', lambda **kwargs: _collection(external_reference='x'))
    with pytest.raises(ValueError, match='idempotency_key collision'): store.append(result, idempotency_key='k')
    monkeypatch.setattr(store, 'get_by_idempotency', lambda **kwargs: None)
    monkeypatch.setattr(store, 'list_for_invoice', lambda *args, **kwargs: ())
    with pytest.raises(sqlite3.IntegrityError): store.append(result)
    monkeypatch.setattr(store, 'list_for_invoice', lambda *args, **kwargs: (result,))
    assert store.append(result) == result
    monkeypatch.setattr(store, 'list_for_invoice', lambda *args, **kwargs: (_collection(external_reference='x'),))
    with pytest.raises(ValueError, match='primary key collision'): store.append(result)


def test_ledger_integrity_race_resolution_matrix(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from contextlib import contextmanager
    store = PlatformSqliteLedgerStore(sqlite_path=str(tmp_path/'ledger-race.sqlite3'))
    posting = _posting()
    class Cursor:
        def fetchone(self): return None
    class Conn:
        def execute(self, sql, params=()):
            if sql.startswith('SELECT payload_json'): return Cursor()
            raise sqlite3.IntegrityError('race')
    @contextmanager
    def connect(): yield Conn()
    monkeypatch.setattr(store, '_connect', connect)
    monkeypatch.setattr(store, 'list_postings', lambda **kwargs: ())
    with pytest.raises(sqlite3.IntegrityError): store.append(posting)
    monkeypatch.setattr(store, 'list_postings', lambda **kwargs: (posting,))
    assert store.append(posting) == posting
    different = _posting(entries=(_entry('d2','debit','cash',amount=101), _entry('c2','credit','revenue',amount=101)))
    monkeypatch.setattr(store, 'list_postings', lambda **kwargs: (different,))
    with pytest.raises(ValueError, match='posting_id collision'): store.append(posting)


def test_idempotency_race_after_preflight_for_all_recovery_and_collection_stores(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from contextlib import contextmanager
    class SelectNone:
        def fetchone(self): return None
    class RecoveryConn:
        def execute(self, sql, params=()):
            if sql.startswith('SELECT payload_json'): return SelectNone()
            raise sqlite3.IntegrityError('race')
    class CollectionConn:
        def execute(self, *args, **kwargs): raise sqlite3.IntegrityError('race')
    @contextmanager
    def recovery_connect(): yield RecoveryConn()
    @contextmanager
    def collection_connect(): yield CollectionConn()

    refund = _refund(); refund_store = PlatformSqliteRefundStore(sqlite_path=str(tmp_path/'rr.sqlite3'), result_cls=RefundResult)
    monkeypatch.setattr(refund_store, '_connect', recovery_connect)
    calls = iter((None, refund))
    monkeypatch.setattr(refund_store, 'get_by_idempotency', lambda **kwargs: next(calls))
    assert refund_store.save(refund, idempotency_key='k') == refund
    calls = iter((None, _refund(amount_minor=101)))
    monkeypatch.setattr(refund_store, 'get_by_idempotency', lambda **kwargs: next(calls))
    with pytest.raises(ValueError, match='idempotency_key collision'): refund_store.save(refund, idempotency_key='k')

    case = _case(); charge_store = PlatformSqliteChargebackStore(sqlite_path=str(tmp_path/'cr.sqlite3'), case_cls=ChargebackCase)
    monkeypatch.setattr(charge_store, '_connect', recovery_connect)
    calls = iter((None, case))
    monkeypatch.setattr(charge_store, 'get_by_idempotency', lambda **kwargs: next(calls))
    assert charge_store.save(case, idempotency_key='k') == case
    calls = iter((None, _case(amount_minor=101)))
    monkeypatch.setattr(charge_store, 'get_by_idempotency', lambda **kwargs: next(calls))
    with pytest.raises(ValueError, match='idempotency'): charge_store.save(case, idempotency_key='k')

    result = _collection(); collection_store = PlatformSqliteCollectionResultStore(sqlite_path=str(tmp_path/'cor.sqlite3'))
    monkeypatch.setattr(collection_store, '_connect', collection_connect)
    calls = iter((None, result))
    monkeypatch.setattr(collection_store, 'get_by_idempotency', lambda **kwargs: next(calls))
    assert collection_store.append(result, idempotency_key='k') == result
    calls = iter((None, _collection(external_reference='x')))
    monkeypatch.setattr(collection_store, 'get_by_idempotency', lambda **kwargs: next(calls))
    with pytest.raises(ValueError, match='idempotency_key collision'): collection_store.append(result, idempotency_key='k')


def test_collection_race_scans_past_non_matching_rows(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from contextlib import contextmanager
    store = PlatformSqliteCollectionResultStore(sqlite_path=str(tmp_path/'scan.sqlite3'))
    result = _collection()
    class Conn:
        def execute(self, *args, **kwargs): raise sqlite3.IntegrityError('race')
    @contextmanager
    def connect(): yield Conn()
    monkeypatch.setattr(store, '_connect', connect)
    first = _collection(processed_at=NOW-timedelta(seconds=1), provider_name='other', external_reference='old')
    monkeypatch.setattr(store, 'list_for_invoice', lambda *args, **kwargs: (first, result))
    assert store.append(result) == result


def test_idempotency_race_falls_through_to_primary_identity_resolution(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from contextlib import contextmanager
    class SelectNone:
        def fetchone(self): return None
    class RecoveryConn:
        def execute(self, sql, params=()):
            if sql.startswith('SELECT payload_json'): return SelectNone()
            raise sqlite3.IntegrityError('race')
    class CollectionConn:
        def execute(self, *args, **kwargs): raise sqlite3.IntegrityError('race')
    @contextmanager
    def recovery_connect(): yield RecoveryConn()
    @contextmanager
    def collection_connect(): yield CollectionConn()

    refund = _refund(); store = PlatformSqliteRefundStore(sqlite_path=str(tmp_path/'rfall.sqlite3'), result_cls=RefundResult)
    monkeypatch.setattr(store, '_connect', recovery_connect)
    monkeypatch.setattr(store, 'get_by_idempotency', lambda **kwargs: None)
    monkeypatch.setattr(store, 'list_for_invoice', lambda **kwargs: (refund,))
    assert store.save(refund, idempotency_key='k') == refund

    case = _case(); cstore = PlatformSqliteChargebackStore(sqlite_path=str(tmp_path/'cfall.sqlite3'), case_cls=ChargebackCase)
    monkeypatch.setattr(cstore, '_connect', recovery_connect)
    monkeypatch.setattr(cstore, 'get_by_idempotency', lambda **kwargs: None)
    monkeypatch.setattr(cstore, 'list_for_invoice', lambda **kwargs: (case,))
    assert cstore.save(case, idempotency_key='k') == case

    result = _collection(); coll = PlatformSqliteCollectionResultStore(sqlite_path=str(tmp_path/'cofall.sqlite3'))
    monkeypatch.setattr(coll, '_connect', collection_connect)
    monkeypatch.setattr(coll, 'get_by_idempotency', lambda **kwargs: None)
    monkeypatch.setattr(coll, 'list_for_invoice', lambda *args, **kwargs: (result,))
    assert coll.append(result, idempotency_key='k') == result

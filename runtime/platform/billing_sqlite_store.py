from __future__ import annotations

import json
import sqlite3
from sqlite3 import IntegrityError
from contextlib import contextmanager
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Iterator

from billing.commercial_cycle_contract import CommercialCollectionResult
from billing.ledger_event import LedgerEntry, LedgerPosting
from billing.ledger_store import LedgerStoreContract
from core.tenancy.normalization import require_tenant_id


CANON_PLATFORM_BILLING_SQLITE_STORE = True
SCHEMA_VERSION = 1


class PlatformSqliteCollectionResultStore:
    def __init__(self, *, sqlite_path: str) -> None:
        self._path = str(sqlite_path)
        if not self._path.strip():
            raise ValueError('sqlite_path is required')
        Path(self._path).parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self._path)
        conn.execute('PRAGMA foreign_keys = ON')
        conn.execute('PRAGMA journal_mode = WAL')
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute('CREATE TABLE IF NOT EXISTS billing_schema_version (component TEXT PRIMARY KEY, version INTEGER NOT NULL)')
            row = conn.execute('SELECT version FROM billing_schema_version WHERE component = ?', ('collection_results',)).fetchone()
            if row is None:
                conn.execute('INSERT INTO billing_schema_version(component, version) VALUES (?, ?)', ('collection_results', SCHEMA_VERSION))
            elif int(row[0]) != SCHEMA_VERSION:
                raise RuntimeError('unsupported collection_results schema version')
            conn.execute(
                '''
                CREATE TABLE IF NOT EXISTS billing_collection_results (
                    tenant_id TEXT NOT NULL,
                    invoice_id TEXT NOT NULL,
                    idempotency_key TEXT,
                    provider_name TEXT NOT NULL,
                    successful INTEGER NOT NULL,
                    external_reference TEXT,
                    failure_reason TEXT,
                    retryable INTEGER NOT NULL,
                    processed_at TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    PRIMARY KEY (tenant_id, invoice_id, processed_at, provider_name)
                )
                '''
            )
            conn.execute(
                'CREATE UNIQUE INDEX IF NOT EXISTS idx_billing_collection_idem ON billing_collection_results(tenant_id, invoice_id, idempotency_key) WHERE idempotency_key IS NOT NULL'
            )

    def append(self, result: CommercialCollectionResult, *, idempotency_key: str | None = None) -> CommercialCollectionResult:
        result.validate()
        tenant_id = require_tenant_id(result.tenant_id)
        invoice_id = str(result.invoice_id).strip()
        idem = None if idempotency_key is None else str(idempotency_key).strip()
        if idem:
            existing = self.get_by_idempotency(tenant_id=tenant_id, invoice_id=invoice_id, idempotency_key=idem)
            if existing is not None:
                if existing != result:
                    raise ValueError('idempotency_key collision for different collection result')
                return existing
        try:
            with self._connect() as conn:
                payload = asdict(result)
                payload['processed_at'] = result.processed_at.isoformat()
                conn.execute(
                    '''
                    INSERT INTO billing_collection_results(
                        tenant_id, invoice_id, idempotency_key, provider_name, successful,
                        external_reference, failure_reason, retryable, processed_at,
                        payload_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''',
                    (
                        tenant_id,
                        invoice_id,
                        idem,
                        str(result.provider_name).strip(),
                        1 if result.successful else 0,
                        result.external_reference,
                        result.failure_reason,
                        1 if result.retryable else 0,
                        result.processed_at.isoformat(),
                        json.dumps(payload, sort_keys=True),
                    ),
                )
        except IntegrityError:
            if idem:
                existing = self.get_by_idempotency(tenant_id=tenant_id, invoice_id=invoice_id, idempotency_key=idem)
                if existing is not None:
                    if existing != result:
                        raise ValueError('idempotency_key collision for different collection result')
                    return existing
            existing_rows = self.list_for_invoice(invoice_id, tenant_id=tenant_id)
            for existing in existing_rows:
                if existing.processed_at == result.processed_at and existing.provider_name == result.provider_name:
                    if existing != result:
                        raise ValueError('collection result primary key collision for different payload')
                    return existing
            raise
        return result

    def get_by_idempotency(self, *, tenant_id: str, invoice_id: str, idempotency_key: str) -> CommercialCollectionResult | None:
        tid = require_tenant_id(tenant_id)
        iid = str(invoice_id).strip()
        idem = str(idempotency_key).strip()
        if not iid or not idem:
            raise ValueError('invoice_id and idempotency_key are required')
        with self._connect() as conn:
            row = conn.execute(
                'SELECT payload_json FROM billing_collection_results WHERE tenant_id = ? AND invoice_id = ? AND idempotency_key = ?',
                (tid, iid, idem),
            ).fetchone()
        return None if row is None else self._decode_result_payload(row[0])

    def list_for_invoice(self, invoice_id: str, *, tenant_id: str | None = None) -> tuple[CommercialCollectionResult, ...]:
        iid = str(invoice_id).strip()
        if not iid:
            raise ValueError('invoice_id is required')
        query = 'SELECT payload_json FROM billing_collection_results WHERE invoice_id = ?'
        params: tuple[object, ...] = (iid,)
        if tenant_id is not None:
            query += ' AND tenant_id = ?'
            params = (iid, require_tenant_id(tenant_id))
        query += ' ORDER BY processed_at ASC, provider_name ASC'
        with self._connect() as conn:
            rows = conn.execute(query, params).fetchall()
        return tuple(self._decode_result_payload(row[0]) for row in rows)

    def _decode_result_payload(self, payload_json: str) -> CommercialCollectionResult:
        payload = json.loads(payload_json)
        payload['processed_at'] = datetime.fromisoformat(payload['processed_at'])
        result = CommercialCollectionResult(**payload)
        result.validate()
        return result


class PlatformSqliteLedgerStore(LedgerStoreContract):
    def __init__(self, *, sqlite_path: str) -> None:
        self._path = str(sqlite_path)
        if not self._path.strip():
            raise ValueError('sqlite_path is required')
        Path(self._path).parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self._path)
        conn.execute('PRAGMA foreign_keys = ON')
        conn.execute('PRAGMA journal_mode = WAL')
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute('CREATE TABLE IF NOT EXISTS billing_schema_version (component TEXT PRIMARY KEY, version INTEGER NOT NULL)')
            row = conn.execute('SELECT version FROM billing_schema_version WHERE component = ?', ('ledger_postings',)).fetchone()
            if row is None:
                conn.execute('INSERT INTO billing_schema_version(component, version) VALUES (?, ?)', ('ledger_postings', SCHEMA_VERSION))
            elif int(row[0]) != SCHEMA_VERSION:
                raise RuntimeError('unsupported ledger_postings schema version')
            conn.execute(
                '''
                CREATE TABLE IF NOT EXISTS billing_ledger_postings (
                    tenant_id TEXT NOT NULL,
                    posting_id TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    PRIMARY KEY (tenant_id, posting_id)
                )
                '''
            )

    def append(self, posting: LedgerPosting) -> LedgerPosting:
        posting.validate()
        tenant_id = require_tenant_id(posting.tenant_id)
        try:
            with self._connect() as conn:
                row = conn.execute('SELECT payload_json FROM billing_ledger_postings WHERE tenant_id = ? AND posting_id = ?', (tenant_id, posting.posting_id)).fetchone()
                if row is not None:
                    existing = self._decode_posting_payload(row[0])
                    if existing != posting:
                        raise ValueError('posting_id collision for different ledger posting')
                    return existing
                payload = asdict(posting)
                payload['entries'] = [
                    {**entry, 'booked_at': entry['booked_at'].isoformat()} if isinstance(entry.get('booked_at'), datetime) else entry
                    for entry in payload['entries']
                ]
                conn.execute(
                    'INSERT INTO billing_ledger_postings(tenant_id, posting_id, payload_json) VALUES (?, ?, ?)',
                    (tenant_id, posting.posting_id, json.dumps(payload, sort_keys=True)),
                )
        except IntegrityError:
            existing = next((item for item in self.list_postings(tenant_id=tenant_id) if item.posting_id == posting.posting_id), None)
            if existing is None:
                raise
            if existing != posting:
                raise ValueError('posting_id collision for different ledger posting')
            return existing
        return posting

    def list_postings(self, *, tenant_id: str) -> tuple[LedgerPosting, ...]:
        tid = require_tenant_id(tenant_id)
        with self._connect() as conn:
            rows = conn.execute('SELECT payload_json FROM billing_ledger_postings WHERE tenant_id = ? ORDER BY posting_id ASC', (tid,)).fetchall()
        return tuple(self._decode_posting_payload(row[0]) for row in rows)

    def total_for_account(self, *, tenant_id: str, account_code: str, side: str | None = None) -> int:
        tid = require_tenant_id(tenant_id)
        code = str(account_code or '').strip()
        if not code:
            raise ValueError('account_code is required')
        normalized_side = None if side is None else str(side).strip().lower()
        if normalized_side is not None and normalized_side not in {'debit', 'credit'}:
            raise ValueError('side must be debit or credit')
        total = 0
        for posting in self.list_postings(tenant_id=tid):
            for entry in posting.entries:
                if entry.account_code != code:
                    continue
                if normalized_side is not None and entry.side.lower() != normalized_side:
                    continue
                total += int(entry.amount_minor)
        return total

    def _decode_posting_payload(self, payload_json: str) -> LedgerPosting:
        payload = json.loads(payload_json)
        entries = []
        for item in payload['entries']:
            item = dict(item)
            item['booked_at'] = datetime.fromisoformat(item['booked_at'])
            entry = LedgerEntry(**item)
            entry.validate()
            entries.append(entry)
        posting = LedgerPosting(
            posting_id=payload['posting_id'],
            tenant_id=payload['tenant_id'],
            reference_type=payload['reference_type'],
            reference_id=payload['reference_id'],
            entries=tuple(entries),
            metadata=dict(payload.get('metadata') or {}),
        )
        posting.validate()
        return posting


__all__ = ['CANON_PLATFORM_BILLING_SQLITE_STORE', 'PlatformSqliteCollectionResultStore', 'PlatformSqliteLedgerStore']

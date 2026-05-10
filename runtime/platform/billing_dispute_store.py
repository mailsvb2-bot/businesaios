from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Iterator

from billing.dispute_policy import DisputeClassification
from core.tenancy.normalization import require_tenant_id

CANON_PLATFORM_BILLING_DISPUTE_STORE = True
DISPUTE_SCHEMA_VERSION = 1


class PlatformSqliteDisputeStore:
    def __init__(self, *, sqlite_path: str, case_cls: type) -> None:
        self._path = str(sqlite_path).strip()
        self._case_cls = case_cls
        if not self._path:
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
            row = conn.execute('SELECT version FROM billing_schema_version WHERE component = ?', ('dispute_store',)).fetchone()
            if row is None:
                conn.execute('INSERT INTO billing_schema_version(component, version) VALUES (?, ?)', ('dispute_store', DISPUTE_SCHEMA_VERSION))
            elif int(row[0]) != DISPUTE_SCHEMA_VERSION:
                raise RuntimeError('unsupported dispute_store schema version')
            conn.execute(
                '''
                CREATE TABLE IF NOT EXISTS billing_dispute_cases (
                    tenant_id TEXT NOT NULL,
                    invoice_id TEXT NOT NULL,
                    case_id TEXT NOT NULL,
                    idempotency_key TEXT,
                    opened_at TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    PRIMARY KEY (tenant_id, case_id)
                )
                '''
            )
            conn.execute('CREATE UNIQUE INDEX IF NOT EXISTS idx_billing_dispute_idem ON billing_dispute_cases(tenant_id, invoice_id, idempotency_key) WHERE idempotency_key IS NOT NULL')

    def save(self, case: Any, *, idempotency_key: str | None = None) -> Any:
        case.validate()
        tid = require_tenant_id(case.tenant_id)
        iid = str(case.invoice_id).strip()
        cid = str(case.case_id).strip()
        idem = None if idempotency_key is None else str(idempotency_key).strip()
        payload_json = json.dumps(self._encode(case), sort_keys=True)
        try:
            with self._connect() as conn:
                row = conn.execute('SELECT payload_json FROM billing_dispute_cases WHERE tenant_id = ? AND case_id = ?', (tid, cid)).fetchone()
                if row is None:
                    conn.execute(
                        'INSERT INTO billing_dispute_cases(tenant_id, invoice_id, case_id, idempotency_key, opened_at, payload_json) VALUES (?, ?, ?, ?, ?, ?)',
                        (tid, iid, cid, idem, case.opened_at.isoformat(), payload_json),
                    )
                    return case
                existing = self._decode(row[0])
                if existing.invoice_id != iid:
                    raise ValueError('dispute case_id collision')
                conn.execute(
                    'UPDATE billing_dispute_cases SET invoice_id = ?, idempotency_key = ?, opened_at = ?, payload_json = ? WHERE tenant_id = ? AND case_id = ?',
                    (iid, idem, case.opened_at.isoformat(), payload_json, tid, cid),
                )
                return case
        except sqlite3.IntegrityError:
            if idem:
                existing = self.get_by_idempotency(tenant_id=tid, invoice_id=iid, idempotency_key=idem)
                if existing is not None:
                    if existing != case:
                        raise ValueError('dispute idempotency collision')
                    return existing
            existing = self.get(tenant_id=tid, case_id=cid)
            if existing is None:
                raise
            if existing != case:
                raise ValueError('dispute case collision')
            return existing

    def get_by_idempotency(self, *, tenant_id: str, invoice_id: str, idempotency_key: str) -> Any | None:
        tid = require_tenant_id(tenant_id)
        iid = str(invoice_id).strip()
        idem = str(idempotency_key).strip()
        if not iid or not idem:
            raise ValueError('invoice_id and idempotency_key are required')
        with self._connect() as conn:
            row = conn.execute('SELECT payload_json FROM billing_dispute_cases WHERE tenant_id = ? AND invoice_id = ? AND idempotency_key = ?', (tid, iid, idem)).fetchone()
        return None if row is None else self._decode(row[0])

    def get(self, *, tenant_id: str, case_id: str) -> Any | None:
        tid = require_tenant_id(tenant_id)
        cid = str(case_id).strip()
        if not cid:
            raise ValueError('case_id is required')
        with self._connect() as conn:
            row = conn.execute('SELECT payload_json FROM billing_dispute_cases WHERE tenant_id = ? AND case_id = ?', (tid, cid)).fetchone()
        return None if row is None else self._decode(row[0])

    def list_for_invoice(self, *, tenant_id: str, invoice_id: str) -> tuple[Any, ...]:
        tid = require_tenant_id(tenant_id)
        iid = str(invoice_id).strip()
        if not iid:
            raise ValueError('invoice_id is required')
        with self._connect() as conn:
            rows = conn.execute('SELECT payload_json FROM billing_dispute_cases WHERE tenant_id = ? AND invoice_id = ? ORDER BY opened_at ASC, case_id ASC', (tid, iid)).fetchall()
        return tuple(self._decode(row[0]) for row in rows)

    @staticmethod
    def _encode(case: Any) -> dict[str, object]:
        return {
            'tenant_id': case.tenant_id,
            'invoice_id': case.invoice_id,
            'case_id': case.case_id,
            'classification': {
                'case_type': case.classification.case_type,
                'severity': case.classification.severity,
                'metadata': dict(case.classification.metadata),
            },
            'status': case.status,
            'idempotency_key': case.idempotency_key,
            'opened_at': case.opened_at.isoformat(),
            'resolved_at': None if case.resolved_at is None else case.resolved_at.isoformat(),
            'resolution': case.resolution,
            'metadata': dict(case.metadata),
        }

    def _decode(self, payload_json: str) -> Any:
        payload = json.loads(payload_json)
        payload['classification'] = DisputeClassification(**payload['classification'])
        payload['opened_at'] = datetime.fromisoformat(payload['opened_at'])
        if payload['resolved_at'] is not None:
            payload['resolved_at'] = datetime.fromisoformat(payload['resolved_at'])
        case = self._case_cls(**payload)
        case.validate()
        return case


__all__ = ['CANON_PLATFORM_BILLING_DISPUTE_STORE', 'DISPUTE_SCHEMA_VERSION', 'PlatformSqliteDisputeStore']

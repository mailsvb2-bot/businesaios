from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any

from core.tenancy.normalization import require_tenant_id

CANON_PLATFORM_BILLING_RECOVERY_STORE = True
SCHEMA_VERSION = 1


class PlatformSqliteRefundStore:
    def __init__(self, *, sqlite_path: str, result_cls: type) -> None:
        self._path = str(sqlite_path).strip()
        self._result_cls = result_cls
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
            row = conn.execute('SELECT version FROM billing_schema_version WHERE component = ?', ('refund_results',)).fetchone()
            if row is None:
                conn.execute('INSERT INTO billing_schema_version(component, version) VALUES (?, ?)', ('refund_results', SCHEMA_VERSION))
            elif int(row[0]) != SCHEMA_VERSION:
                raise RuntimeError('unsupported refund_results schema version')
            conn.execute(
                '''
                CREATE TABLE IF NOT EXISTS billing_refund_results (
                    tenant_id TEXT NOT NULL,
                    invoice_id TEXT NOT NULL,
                    refund_id TEXT NOT NULL,
                    idempotency_key TEXT,
                    processed_at TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    PRIMARY KEY (tenant_id, refund_id)
                )
                '''
            )
            conn.execute('CREATE UNIQUE INDEX IF NOT EXISTS idx_billing_refund_idem ON billing_refund_results(tenant_id, invoice_id, idempotency_key) WHERE idempotency_key IS NOT NULL')

    def save(self, result: Any, *, idempotency_key: str | None = None) -> Any:
        result.validate()
        tenant_id = require_tenant_id(result.tenant_id)
        invoice_id = str(result.invoice_id).strip()
        refund_id = str(result.refund_id).strip()
        idem = None if idempotency_key is None else (str(idempotency_key).strip() or None)
        if idem:
            existing = self.get_by_idempotency(tenant_id=tenant_id, invoice_id=invoice_id, idempotency_key=idem)
            if existing is not None:
                if existing != result:
                    raise ValueError('idempotency_key collision for different refund result')
                return existing
        payload = {
            'tenant_id': result.tenant_id,
            'invoice_id': result.invoice_id,
            'refund_id': result.refund_id,
            'amount_minor': result.amount_minor,
            'currency': result.currency,
            'provider_name': result.provider_name,
            'external_reference': result.external_reference,
            'processed_at': result.processed_at.isoformat(),
            'metadata': dict(result.metadata),
        }
        try:
            with self._connect() as conn:
                row = conn.execute('SELECT payload_json FROM billing_refund_results WHERE tenant_id = ? AND refund_id = ?', (tenant_id, refund_id)).fetchone()
                if row is not None:
                    existing = self._decode_result_payload(row[0])
                    if existing != result:
                        raise ValueError('refund_id collision for different refund result')
                    return existing
                conn.execute(
                    'INSERT INTO billing_refund_results(tenant_id, invoice_id, refund_id, idempotency_key, processed_at, payload_json) VALUES (?, ?, ?, ?, ?, ?)',
                    (tenant_id, invoice_id, refund_id, idem, result.processed_at.isoformat(), json.dumps(payload, sort_keys=True)),
                )
        except sqlite3.IntegrityError:
            if idem:
                existing = self.get_by_idempotency(tenant_id=tenant_id, invoice_id=invoice_id, idempotency_key=idem)
                if existing is not None:
                    if existing != result:
                        raise ValueError('idempotency_key collision for different refund result')
                    return existing
            existing = next((item for item in self.list_for_invoice(tenant_id=tenant_id, invoice_id=invoice_id) if item.refund_id == refund_id), None)
            if existing is None:
                raise
            if existing != result:
                raise ValueError('refund_id collision for different refund result')
            return existing
        return result

    def get_by_idempotency(self, *, tenant_id: str, invoice_id: str, idempotency_key: str) -> Any | None:
        tid = require_tenant_id(tenant_id)
        iid = str(invoice_id).strip()
        idem = str(idempotency_key).strip()
        if not iid or not idem:
            raise ValueError('invoice_id and idempotency_key are required')
        with self._connect() as conn:
            row = conn.execute('SELECT payload_json FROM billing_refund_results WHERE tenant_id = ? AND invoice_id = ? AND idempotency_key = ?', (tid, iid, idem)).fetchone()
        return None if row is None else self._decode_result_payload(row[0])

    def list_for_invoice(self, *, tenant_id: str, invoice_id: str) -> tuple[Any, ...]:
        tid = require_tenant_id(tenant_id)
        iid = str(invoice_id).strip()
        if not iid:
            raise ValueError('invoice_id is required')
        with self._connect() as conn:
            rows = conn.execute('SELECT payload_json FROM billing_refund_results WHERE tenant_id = ? AND invoice_id = ? ORDER BY processed_at ASC, refund_id ASC', (tid, iid)).fetchall()
        return tuple(self._decode_result_payload(row[0]) for row in rows)

    def _decode_result_payload(self, payload_json: str) -> Any:
        payload = json.loads(payload_json)
        payload['processed_at'] = datetime.fromisoformat(payload['processed_at'])
        result = self._result_cls(**payload)
        result.validate()
        return result


class PlatformSqliteChargebackStore:
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
            row = conn.execute('SELECT version FROM billing_schema_version WHERE component = ?', ('chargeback_cases',)).fetchone()
            if row is None:
                conn.execute('INSERT INTO billing_schema_version(component, version) VALUES (?, ?)', ('chargeback_cases', SCHEMA_VERSION))
            elif int(row[0]) != SCHEMA_VERSION:
                raise RuntimeError('unsupported chargeback_cases schema version')
            conn.execute(
                '''
                CREATE TABLE IF NOT EXISTS billing_chargeback_cases (
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
            conn.execute('CREATE UNIQUE INDEX IF NOT EXISTS idx_billing_chargeback_idem ON billing_chargeback_cases(tenant_id, invoice_id, idempotency_key) WHERE idempotency_key IS NOT NULL')

    def save(self, case: Any, *, idempotency_key: str | None = None) -> Any:
        case.validate()
        tenant_id = require_tenant_id(case.tenant_id)
        invoice_id = str(case.invoice_id).strip()
        case_id = str(case.case_id).strip()
        idem = None if idempotency_key is None else (str(idempotency_key).strip() or None)
        if idem:
            existing = self.get_by_idempotency(tenant_id=tenant_id, invoice_id=invoice_id, idempotency_key=idem)
            if existing is not None:
                if existing != case:
                    raise ValueError('chargeback idempotency collision')
                return existing
        payload = {
            'tenant_id': case.tenant_id,
            'invoice_id': case.invoice_id,
            'user_id': case.user_id,
            'amount_minor': case.amount_minor,
            'currency': case.currency,
            'reason': case.reason,
            'opened_at': case.opened_at.isoformat(),
            'case_id': case.case_id,
            'idempotency_key': case.idempotency_key,
            'metadata': dict(case.metadata),
        }
        try:
            with self._connect() as conn:
                row = conn.execute('SELECT payload_json FROM billing_chargeback_cases WHERE tenant_id = ? AND case_id = ?', (tenant_id, case_id)).fetchone()
                if row is not None:
                    existing = self._decode_case_payload(row[0])
                    if existing != case:
                        raise ValueError('chargeback case collision')
                    return existing
                conn.execute(
                    'INSERT INTO billing_chargeback_cases(tenant_id, invoice_id, case_id, idempotency_key, opened_at, payload_json) VALUES (?, ?, ?, ?, ?, ?)',
                    (tenant_id, invoice_id, case_id, idem, case.opened_at.isoformat(), json.dumps(payload, sort_keys=True)),
                )
        except sqlite3.IntegrityError:
            if idem:
                existing = self.get_by_idempotency(tenant_id=tenant_id, invoice_id=invoice_id, idempotency_key=idem)
                if existing is not None:
                    if existing != case:
                        raise ValueError('chargeback idempotency collision')
                    return existing
            existing = next((item for item in self.list_for_invoice(tenant_id=tenant_id, invoice_id=invoice_id) if item.case_id == case_id), None)
            if existing is None:
                raise
            if existing != case:
                raise ValueError('chargeback case collision')
            return existing
        return case

    def get_by_idempotency(self, *, tenant_id: str, invoice_id: str, idempotency_key: str) -> Any | None:
        tid = require_tenant_id(tenant_id)
        iid = str(invoice_id).strip()
        idem = str(idempotency_key).strip()
        if not iid or not idem:
            raise ValueError('invoice_id and idempotency_key are required')
        with self._connect() as conn:
            row = conn.execute('SELECT payload_json FROM billing_chargeback_cases WHERE tenant_id = ? AND invoice_id = ? AND idempotency_key = ?', (tid, iid, idem)).fetchone()
        return None if row is None else self._decode_case_payload(row[0])

    def list_for_invoice(self, *, tenant_id: str, invoice_id: str) -> tuple[Any, ...]:
        tid = require_tenant_id(tenant_id)
        iid = str(invoice_id).strip()
        if not iid:
            raise ValueError('invoice_id is required')
        with self._connect() as conn:
            rows = conn.execute('SELECT payload_json FROM billing_chargeback_cases WHERE tenant_id = ? AND invoice_id = ? ORDER BY opened_at ASC, case_id ASC', (tid, iid)).fetchall()
        return tuple(self._decode_case_payload(row[0]) for row in rows)

    def _decode_case_payload(self, payload_json: str) -> Any:
        payload = json.loads(payload_json)
        payload['opened_at'] = datetime.fromisoformat(payload['opened_at'])
        case = self._case_cls(**payload)
        case.validate()
        return case


__all__ = ['CANON_PLATFORM_BILLING_RECOVERY_STORE', 'SCHEMA_VERSION', 'PlatformSqliteChargebackStore', 'PlatformSqliteRefundStore']

from __future__ import annotations

import json
import os
import sqlite3
import time
from dataclasses import asdict, is_dataclass
from datetime import datetime
from decimal import Decimal
from enum import Enum
from pathlib import Path
from threading import RLock

from runtime.platform.outbox.sqlite_pragmas import configure_sqlite, is_prod_env


CANON_CLIENT_OUTCOME_SQLITE_PERSISTENCE = True
CANON_CLIENT_OUTCOME_SINGLE_REPLICA_FAIL_CLOSED = True


def client_outcome_db_path() -> Path:
    explicit = str(os.getenv('BUSINESAIOS_CLIENT_OUTCOME_DB_PATH', '') or '').strip()
    if explicit:
        path = Path(explicit)
    else:
        data_dir = Path(str(os.getenv('DATA_DIR', 'data') or 'data').strip() or 'data')
        path = data_dir / 'client_outcome' / 'client_outcome.sqlite3'
    if is_prod_env() and str(path).strip() in {'', ':memory:'}:
        raise RuntimeError('PRODUCTION_CLIENT_OUTCOME_PERSISTENT_DB_REQUIRED')
    return path


def enforce_client_outcome_replica_contract() -> None:
    counts: list[int] = []
    for name in ('BUSINESAIOS_REPLICA_COUNT', 'WEB_CONCURRENCY', 'UVICORN_WORKERS'):
        raw = str(os.getenv(name, '') or '').strip()
        if not raw:
            continue
        try:
            counts.append(int(raw))
        except ValueError as exc:
            raise RuntimeError(f'INVALID_{name}') from exc
    if counts and max(counts) > 1:
        raise RuntimeError('CLIENT_OUTCOME_SQLITE_REQUIRES_SINGLE_REPLICA_EXTERNAL_STORE_REQUIRED')


def _json_default(value: object) -> object:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, Enum):
        return value.value
    if is_dataclass(value):
        return asdict(value)
    if isinstance(value, (set, frozenset, tuple)):
        return list(value)
    raise TypeError(f'unsupported persistent payload type: {type(value).__name__}')


def _json_dumps(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), default=_json_default)


def _json_loads(value: str) -> object:
    return json.loads(str(value))


class _SQLiteOwner:
    def __init__(self, path: str | Path | None = None) -> None:
        enforce_client_outcome_replica_contract()
        self.path = Path(path) if path is not None else client_outcome_db_path()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = RLock()
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.path), timeout=30.0, check_same_thread=False)
        configure_sqlite(conn, prod=is_prod_env())
        return conn

    def _initialize(self) -> None:
        with self._lock, self._connect() as conn:
            conn.executescript(
                '''
                CREATE TABLE IF NOT EXISTS client_outcome_registry (
                    namespace TEXT NOT NULL,
                    item_key TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    updated_at_epoch_ms INTEGER NOT NULL,
                    PRIMARY KEY(namespace, item_key)
                );
                CREATE TABLE IF NOT EXISTS client_outcome_ledger_postings (
                    tenant_id TEXT NOT NULL,
                    posting_id TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    created_at_epoch_ms INTEGER NOT NULL,
                    PRIMARY KEY(tenant_id, posting_id)
                );
                CREATE TABLE IF NOT EXISTS client_outcome_metric_samples (
                    sample_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    tenant_id TEXT NOT NULL,
                    metric_name TEXT NOT NULL,
                    kind TEXT NOT NULL,
                    value REAL NOT NULL,
                    aggregation TEXT NOT NULL,
                    emitted_at TEXT NOT NULL,
                    labels_json TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_client_outcome_metrics_lookup
                    ON client_outcome_metric_samples(tenant_id, metric_name, emitted_at);
                '''
            )


class SQLiteJsonRegistryBackend:
    def __init__(self, *, namespace: str, owner: _SQLiteOwner) -> None:
        self._namespace = str(namespace).strip()
        if not self._namespace:
            raise ValueError('namespace is required')
        self._owner = owner

    def replace(self, key: str, value: object) -> None:
        normalized = str(key).strip()
        if not normalized:
            raise ValueError('registry key is required')
        payload = _json_dumps(value)
        with self._owner._lock, self._owner._connect() as conn:
            conn.execute('BEGIN IMMEDIATE')
            conn.execute(
                '''
                INSERT INTO client_outcome_registry(namespace, item_key, payload_json, updated_at_epoch_ms)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(namespace, item_key) DO UPDATE SET
                    payload_json=excluded.payload_json,
                    updated_at_epoch_ms=excluded.updated_at_epoch_ms
                ''',
                (self._namespace, normalized, payload, int(time.time() * 1000)),
            )
            conn.commit()

    def register_unique(self, key: str, value: object) -> None:
        normalized = str(key).strip()
        if not normalized:
            raise ValueError('registry key is required')
        payload = _json_dumps(value)
        try:
            with self._owner._lock, self._owner._connect() as conn:
                conn.execute('BEGIN IMMEDIATE')
                conn.execute(
                    '''
                    INSERT INTO client_outcome_registry(namespace, item_key, payload_json, updated_at_epoch_ms)
                    VALUES (?, ?, ?, ?)
                    ''',
                    (self._namespace, normalized, payload, int(time.time() * 1000)),
                )
                conn.commit()
        except sqlite3.IntegrityError as exc:
            raise ValueError(f'duplicate registry key: {normalized}') from exc

    def get(self, key: str) -> object:
        normalized = str(key).strip()
        with self._owner._lock, self._owner._connect() as conn:
            row = conn.execute(
                'SELECT payload_json FROM client_outcome_registry WHERE namespace=? AND item_key=?',
                (self._namespace, normalized),
            ).fetchone()
        if row is None:
            raise KeyError(normalized)
        return _json_loads(str(row[0]))

    def maybe_get(self, key: str) -> object | None:
        try:
            return self.get(key)
        except KeyError:
            return None

    def items(self) -> tuple[tuple[str, object], ...]:
        with self._owner._lock, self._owner._connect() as conn:
            rows = conn.execute(
                'SELECT item_key, payload_json FROM client_outcome_registry WHERE namespace=? ORDER BY item_key',
                (self._namespace,),
            ).fetchall()
        return tuple((str(key), _json_loads(str(payload))) for key, payload in rows)


__all__ = [
    'CANON_CLIENT_OUTCOME_SINGLE_REPLICA_FAIL_CLOSED',
    'CANON_CLIENT_OUTCOME_SQLITE_PERSISTENCE',
    'SQLiteJsonRegistryBackend',
    '_SQLiteOwner',
    'client_outcome_db_path',
    'enforce_client_outcome_replica_contract',
]

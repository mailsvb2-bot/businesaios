"""Durable route history for queue remediation surfaces.

This module records access to queue remediation control-plane surfaces:
- queue ops view reads
- remediation audit reads
- remediation hook execution requests

It is evidence only and must never mutate queue execution state.
"""

from __future__ import annotations

import importlib
import json
import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from threading import RLock

from core.tenancy.normalization import require_tenant_id
from runtime.platform.outbox.sqlite_pragmas import configure_sqlite, is_prod_env
from runtime.queue.job_contract import normalize_now

sqlite3 = importlib.import_module("sqlite3")

CANON_RUNTIME_QUEUE_REMEDIATION_ROUTE_HISTORY_SQLITE = True


def runtime_queue_remediation_route_history_store_path() -> Path:
    explicit = os.getenv('BUSINESAIOS_QUEUE_REMEDIATION_ROUTE_HISTORY_SQLITE_PATH', '').strip()
    if explicit:
        return Path(explicit)
    data_dir = os.getenv('DATA_DIR', 'data').strip() or 'data'
    return Path(data_dir) / 'runtime' / 'queue_remediation_route_history.sqlite3'


@dataclass(frozen=True)
class QueueRemediationRouteHistoryEntry:
    tenant_id: str
    queue_name: str
    action: str
    source: str
    actor_id: str | None
    request_id: str | None
    status: str
    metadata: dict[str, object]
    recorded_at: datetime


class SqliteQueueRemediationRouteHistoryStore:
    def __init__(self, path: str | Path | None = None, *, busy_timeout_ms: int = 5000) -> None:
        self._path = Path(path) if path is not None else runtime_queue_remediation_route_history_store_path()
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._busy_timeout_ms = max(100, int(busy_timeout_ms))
        self._lock = RLock()
        self._closed = False
        self._init_schema()

    def close(self) -> None:
        with self._lock:
            self._closed = True

    def record(
        self,
        *,
        tenant_id: str,
        queue_name: str,
        action: str,
        source: str,
        status: str,
        metadata: dict[str, object] | None = None,
        actor_id: str | None = None,
        request_id: str | None = None,
        recorded_at: datetime | None = None,
    ) -> QueueRemediationRouteHistoryEntry:
        self._ensure_open()
        normalized_tenant_id = require_tenant_id(tenant_id)
        normalized_queue_name = str(queue_name or '').strip()
        normalized_action = str(action or '').strip()
        if not normalized_queue_name:
            raise ValueError('queue_name is required')
        if not normalized_action:
            raise ValueError('action is required')
        entry = QueueRemediationRouteHistoryEntry(
            tenant_id=normalized_tenant_id,
            queue_name=normalized_queue_name,
            action=normalized_action,
            source=str(source).strip() or 'control_plane',
            actor_id=(str(actor_id).strip() or None) if actor_id is not None else None,
            request_id=(str(request_id).strip() or None) if request_id is not None else None,
            status=str(status).strip() or 'ok',
            metadata=dict(metadata or {}),
            recorded_at=normalize_now(recorded_at),
        )
        with self._lock, self._connect() as db:
            db.execute('BEGIN IMMEDIATE;')
            db.execute(
                '''
                INSERT INTO runtime_queue_remediation_route_history (
                    tenant_id,
                    queue_name,
                    action,
                    source,
                    actor_id,
                    request_id,
                    status,
                    metadata_json,
                    recorded_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''',
                (
                    entry.tenant_id,
                    entry.queue_name,
                    entry.action,
                    entry.source,
                    entry.actor_id,
                    entry.request_id,
                    entry.status,
                    json.dumps(entry.metadata, ensure_ascii=False, separators=(",", ":")),
                    entry.recorded_at.isoformat(),
                ),
            )
            db.commit()
        return entry

    def list_entries(
        self,
        *,
        tenant_id: str,
        queue_name: str,
        limit: int = 100,
        action: str | None = None,
        status: str | None = None,
        source: str | None = None,
    ) -> tuple[QueueRemediationRouteHistoryEntry, ...]:
        self._ensure_open()
        normalized_tenant_id = require_tenant_id(tenant_id)
        normalized_queue_name = str(queue_name).strip()
        if not normalized_queue_name:
            raise ValueError('queue_name is required')
        normalized_limit = max(1, int(limit))
        clauses = ['tenant_id = ?', 'queue_name = ?']
        params: list[object] = [normalized_tenant_id, normalized_queue_name]
        normalized_action = str(action or '').strip()
        normalized_status = str(status or '').strip()
        normalized_source = str(source or '').strip()
        if normalized_action:
            clauses.append('action = ?')
            params.append(normalized_action)
        if normalized_status:
            clauses.append('status = ?')
            params.append(normalized_status)
        if normalized_source:
            clauses.append('source = ?')
            params.append(normalized_source)
        params.append(normalized_limit)
        query = f'''
                SELECT tenant_id, queue_name, action, source, actor_id, request_id, status, metadata_json, recorded_at
                FROM runtime_queue_remediation_route_history
                WHERE {' AND '.join(clauses)}
                ORDER BY id DESC
                LIMIT ?
                '''
        with self._lock, self._connect() as db:
            rows = db.execute(query, tuple(params)).fetchall()
        return tuple(
            QueueRemediationRouteHistoryEntry(
                tenant_id=str(row['tenant_id']),
                queue_name=str(row['queue_name']),
                action=str(row['action']),
                source=str(row['source']),
                actor_id=None if row['actor_id'] is None else str(row['actor_id']),
                request_id=None if row['request_id'] is None else str(row['request_id']),
                status=str(row['status']),
                metadata=self._decode_metadata(row['metadata_json']),
                recorded_at=normalize_now(datetime.fromisoformat(str(row['recorded_at']))),
            )
            for row in rows
        )

    @staticmethod
    def _decode_metadata(raw: object) -> dict[str, object]:
        try:
            value = json.loads(str(raw) or '{}')
        except Exception:
            return {}
        return dict(value) if isinstance(value, dict) else {}

    def _connect(self) -> sqlite3.Connection:
        db = sqlite3.connect(self._path, timeout=max(0.1, self._busy_timeout_ms / 1000.0), check_same_thread=False)
        db.row_factory = sqlite3.Row
        configure_sqlite(db, prod=is_prod_env())
        db.execute(f'PRAGMA busy_timeout={self._busy_timeout_ms};')
        return db

    def _init_schema(self) -> None:
        with self._lock, self._connect() as db:
            db.executescript(
                '''
                CREATE TABLE IF NOT EXISTS runtime_queue_remediation_route_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    tenant_id TEXT NOT NULL,
                    queue_name TEXT NOT NULL,
                    action TEXT NOT NULL,
                    source TEXT NOT NULL,
                    actor_id TEXT,
                    request_id TEXT,
                    status TEXT NOT NULL,
                    metadata_json TEXT NOT NULL,
                    recorded_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS ix_runtime_queue_remediation_route_history_lookup
                    ON runtime_queue_remediation_route_history (tenant_id, queue_name, action, recorded_at);
                CREATE INDEX IF NOT EXISTS ix_runtime_queue_remediation_route_history_status_source
                    ON runtime_queue_remediation_route_history (tenant_id, queue_name, status, source, recorded_at);
                '''
            )
            db.commit()

    def _ensure_open(self) -> None:
        if self._closed:
            raise RuntimeError('SqliteQueueRemediationRouteHistoryStore is closed')


__all__ = [
    'CANON_RUNTIME_QUEUE_REMEDIATION_ROUTE_HISTORY_SQLITE',
    'QueueRemediationRouteHistoryEntry',
    'SqliteQueueRemediationRouteHistoryStore',
    'runtime_queue_remediation_route_history_store_path',
]

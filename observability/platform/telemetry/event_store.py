from __future__ import annotations

from runtime.service_names import RuntimeServiceName

import importlib
import json
import os
from pathlib import Path
sqlite3 = importlib.import_module("sqlite3")
from typing import Any, Dict, Iterable, Iterator, Sequence

from datetime import datetime, timezone

from boot.bootstrap_config_surface import BootstrapConfigSurface
from governance.persistence_codec import ensure_parent_dir
from observability.observability_store_paths import telemetry_event_store_path
from observability.storage_coordination import advisory_file_lock
from observability.platform.telemetry.event_stream import (
    CANON_PLATFORM_TELEMETRY_EVENT_STREAM,
    EventStoreSink,
    InMemoryEventStore,
    TelemetryEventStore as EventStore,
)
from shared.types import ensure_jsonable, new_id


CANON_PLATFORM_TELEMETRY_EVENT_STORE = True


def _event_store_path(*, config_surface: BootstrapConfigSurface | None = None) -> Path:
    return telemetry_event_store_path(config_surface=config_surface)


def _normalized_event_types(*, event_type: str | None, event_types: Sequence[str] | None) -> set[str] | None:
    if event_types:
        return {str(item).strip() for item in event_types if str(item).strip()}
    if event_type and str(event_type).strip():
        return {str(event_type).strip()}
    return None


def _ts_iso_to_ms(value: str) -> int:
    try:
        dt = datetime.fromisoformat(str(value).replace('Z', '+00:00'))
    except Exception:
        return 0
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return int(dt.timestamp() * 1000)


class JsonlEventStore:
    """Persistent append-only telemetry store."""

    def __init__(self, path: str | Path | None = None, *, config_surface: BootstrapConfigSurface | None = None) -> None:
        self._path = Path(path) if path is not None else _event_store_path(config_surface=config_surface)
        ensure_parent_dir(self._path)
        if not self._path.exists():
            self._path.touch()

    @property
    def path(self) -> Path:
        return self._path

    def close(self) -> None:
        conn = getattr(self, '_conn', None)
        if conn is None:
            return
        self._conn = None
        conn.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    def __del__(self) -> None:  # pragma: no cover
        try:
            self.close()
        except Exception:
            return

    def append(self, *, tenant_id: str, user_id: str | None, event_type: str, payload: Dict[str, Any]) -> None:
        tenant = str(tenant_id or '').strip()
        event_name = str(event_type or '').strip()
        if not tenant:
            raise ValueError('tenant_id is required')
        if not event_name:
            raise ValueError('event_type is required')
        record = {
            'event_id': new_id('evt'),
            'tenant_id': tenant,
            'user_id': None if user_id is None else str(user_id),
            'event_type': event_name,
            'payload': dict(ensure_jsonable(payload or {})),
            'ts_iso': datetime.now(timezone.utc).isoformat(),
        }
        with advisory_file_lock(self._path, exclusive=True):
            with self._path.open('a', encoding='utf-8') as fh:
                fh.write(json.dumps(record, ensure_ascii=False, sort_keys=True))
                fh.write('\n')
                fh.flush()
                os.fsync(fh.fileno())

    def latest_events(
        self,
        *,
        tenant_id: str,
        user_id: str | None = None,
        event_type: str | None = None,
        event_types: Sequence[str] | None = None,
        limit: int = 2000,
    ) -> Iterable[Dict[str, Any]]:
        tenant = str(tenant_id)
        normalized_user = None if user_id is None else str(user_id)
        accepted_types = _normalized_event_types(event_type=event_type, event_types=event_types)
        max_items = max(0, int(limit))
        if max_items == 0:
            return []
        out: list[dict[str, Any]] = []
        for row in reversed(self._read_all()):
            if row.get('tenant_id') != tenant:
                continue
            if normalized_user is not None and row.get('user_id') != normalized_user:
                continue
            if accepted_types is not None and row.get('event_type') not in accepted_types:
                continue
            out.append(dict(row))
            if len(out) >= max_items:
                break
        return out

    def latest_event(
        self,
        *,
        tenant_id: str,
        user_id: str | None = None,
        event_type: str | None = None,
        event_types: Sequence[str] | None = None,
    ) -> Dict[str, Any] | None:
        xs = list(self.latest_events(tenant_id=tenant_id, user_id=user_id, event_type=event_type, event_types=event_types, limit=1))
        return xs[0] if xs else None

    def iter_events(
        self,
        *,
        tenant_id: str,
        user_id: str | None = None,
        event_type: str | None = None,
        event_types: Sequence[str] | None = None,
        start_ms: int | None = None,
        end_ms: int | None = None,
        limit: int | None = None,
    ) -> Iterable[Dict[str, Any]]:
        accepted_types = _normalized_event_types(event_type=event_type, event_types=event_types)
        tenant = str(tenant_id)
        normalized_user = None if user_id is None else str(user_id)
        max_items = None if limit is None else max(0, int(limit))
        out: list[dict[str, Any]] = []
        for row in self._read_all():
            if row.get('tenant_id') != tenant:
                continue
            if normalized_user is not None and row.get('user_id') != normalized_user:
                continue
            if accepted_types is not None and row.get('event_type') not in accepted_types:
                continue
            ts_ms = _ts_iso_to_ms(str(row.get('ts_iso') or ''))
            if start_ms is not None and ts_ms < int(start_ms):
                continue
            if end_ms is not None and ts_ms > int(end_ms):
                continue
            out.append(dict(row))
            if max_items is not None and len(out) >= max_items:
                break
        return out

    def _iter_lines(self) -> Iterator[str]:
        if not self._path.exists():
            return iter(())
        def _generator() -> Iterator[str]:
            with advisory_file_lock(self._path, exclusive=False):
                with self._path.open('r', encoding='utf-8') as handle:
                    for raw_line in handle:
                        line = raw_line.strip()
                        if line:
                            yield line
        return _generator()

    def _read_all(self) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for line in self._iter_lines():
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(row, dict):
                out.append(row)
        return out




class SqliteEventStore:
    """Persistent sqlite-backed telemetry store.

    Uses stdlib sqlite so the project has a real local durable owner instead of
    relying on JSONL or in-memory paths only.
    """

    def __init__(self, path: str | Path | None = None, *, config_surface: BootstrapConfigSurface | None = None) -> None:
        default_path = _event_store_path(config_surface=config_surface)
        self._path = Path(path) if path is not None else default_path.with_suffix('.sqlite3')
        ensure_parent_dir(self._path)
        self._conn = sqlite3.connect(str(self._path))
        self._conn.execute('PRAGMA journal_mode=WAL')
        self._conn.execute('PRAGMA synchronous=NORMAL')
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS telemetry_events (
                event_id TEXT PRIMARY KEY,
                tenant_id TEXT NOT NULL,
                user_id TEXT,
                event_type TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                ts_iso TEXT NOT NULL,
                ts_ms INTEGER NOT NULL
            )
            """
        )
        self._conn.commit()

    @property
    def path(self) -> Path:
        return self._path

    def close(self) -> None:
        conn = getattr(self, '_conn', None)
        if conn is None:
            return
        self._conn = None
        conn.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    def __del__(self) -> None:  # pragma: no cover
        try:
            self.close()
        except Exception:
            return

    def append(self, *, tenant_id: str, user_id: str | None, event_type: str, payload: Dict[str, Any]) -> None:
        tenant = str(tenant_id or '').strip()
        event_name = str(event_type or '').strip()
        if not tenant:
            raise ValueError('tenant_id is required')
        if not event_name:
            raise ValueError('event_type is required')
        ts_iso = datetime.now(timezone.utc).isoformat()
        row = {
            'event_id': new_id('evt'),
            'tenant_id': tenant,
            'user_id': None if user_id is None else str(user_id),
            'event_type': event_name,
            'payload': dict(ensure_jsonable(payload or {})),
            'ts_iso': ts_iso,
        }
        self._conn.execute(
            'INSERT INTO telemetry_events(event_id, tenant_id, user_id, event_type, payload_json, ts_iso, ts_ms) VALUES (?, ?, ?, ?, ?, ?, ?)',
            (row['event_id'], row['tenant_id'], row['user_id'], row['event_type'], json.dumps(row['payload'], ensure_ascii=False, sort_keys=True), row['ts_iso'], _ts_iso_to_ms(ts_iso)),
        )
        self._conn.commit()

    def latest_events(self, *, tenant_id: str, user_id: str | None = None, event_type: str | None = None, event_types: Sequence[str] | None = None, limit: int = 2000) -> Iterable[Dict[str, Any]]:
        tenant = str(tenant_id)
        accepted_types = _normalized_event_types(event_type=event_type, event_types=event_types)
        clauses = ['tenant_id = ?']
        params: list[Any] = [tenant]
        if user_id is not None:
            clauses.append('user_id = ?')
            params.append(str(user_id))
        if accepted_types:
            placeholders = ','.join('?' for _ in accepted_types)
            clauses.append(f'event_type IN ({placeholders})')
            params.extend(sorted(accepted_types))
        sql = 'SELECT event_id, tenant_id, user_id, event_type, payload_json, ts_iso FROM telemetry_events WHERE ' + ' AND '.join(clauses) + ' ORDER BY ts_ms DESC, rowid DESC LIMIT ?'
        params.append(max(0, int(limit)))
        rows = self._conn.execute(sql, tuple(params)).fetchall()
        return [
            {
                'event_id': event_id,
                'tenant_id': tenant_value,
                'user_id': user_value,
                'event_type': event_name,
                'payload': json.loads(payload_json) if payload_json else {},
                'ts_iso': ts_iso,
            }
            for event_id, tenant_value, user_value, event_name, payload_json, ts_iso in rows
        ]

    def latest_event(self, *, tenant_id: str, user_id: str | None = None, event_type: str | None = None, event_types: Sequence[str] | None = None) -> Dict[str, Any] | None:
        xs = list(self.latest_events(tenant_id=tenant_id, user_id=user_id, event_type=event_type, event_types=event_types, limit=1))
        return xs[0] if xs else None

    def iter_events(self, *, tenant_id: str, user_id: str | None = None, event_type: str | None = None, event_types: Sequence[str] | None = None, start_ms: int | None = None, end_ms: int | None = None, limit: int | None = None) -> Iterable[Dict[str, Any]]:
        tenant = str(tenant_id)
        accepted_types = _normalized_event_types(event_type=event_type, event_types=event_types)
        clauses = ['tenant_id = ?']
        params: list[Any] = [tenant]
        if user_id is not None:
            clauses.append('user_id = ?')
            params.append(str(user_id))
        if accepted_types:
            placeholders = ','.join('?' for _ in accepted_types)
            clauses.append(f'event_type IN ({placeholders})')
            params.extend(sorted(accepted_types))
        if start_ms is not None:
            clauses.append('ts_ms >= ?')
            params.append(int(start_ms))
        if end_ms is not None:
            clauses.append('ts_ms <= ?')
            params.append(int(end_ms))
        sql = 'SELECT event_id, tenant_id, user_id, event_type, payload_json, ts_iso FROM telemetry_events WHERE ' + ' AND '.join(clauses) + ' ORDER BY ts_ms ASC, rowid ASC'
        if limit is not None:
            sql += ' LIMIT ?'
            params.append(max(0, int(limit)))
        rows = self._conn.execute(sql, tuple(params)).fetchall()
        out: list[dict[str, Any]] = []
        for event_id, tenant_value, user_value, event_name, payload_json, ts_iso in rows:
            try:
                payload = json.loads(payload_json)
            except json.JSONDecodeError:
                payload = {}
            out.append({
                'event_id': event_id,
                'tenant_id': tenant_value,
                'user_id': user_value,
                'event_type': event_name,
                'payload': payload if isinstance(payload, dict) else {},
                'ts_iso': ts_iso,
            })
        return out


def build_default_event_store(*, backend: str | None = None, path: str | Path | None = None, config_surface: BootstrapConfigSurface | None = None) -> EventStore:
    selected = str(backend or (config_surface.telemetry_event_store_backend if config_surface is not None else os.getenv('BUSINESAIOS_TELEMETRY_EVENT_STORE_BACKEND', 'sqlite'))).strip().lower()
    resolved_path = Path(path) if path is not None else _event_store_path(config_surface=config_surface)
    if selected in {'memory', 'inmemory'}:
        return InMemoryEventStore()
    if selected in {'jsonl', 'file'}:
        return JsonlEventStore(resolved_path)
    return SqliteEventStore(resolved_path)


__all__ = [
    'CANON_PLATFORM_TELEMETRY_EVENT_STORE',
    'CANON_PLATFORM_TELEMETRY_EVENT_STREAM',
    'build_default_event_store',
    'EventStore',
    'EventStoreSink',
    'InMemoryEventStore',
    'JsonlEventStore',
    'SqliteEventStore',
]
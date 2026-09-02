"""Canonical Postgres event-store adapter.

The driver remains sealed behind runtime.platform.postgres_port.PostgresPort.
This adapter mirrors the canonical sqlite event-store append/query semantics used
by runtime boot: append durable events, query governance readers, query latest
events, count events, and provide a health probe. It intentionally keeps
explicit production enablement so capability surfaces cannot be mistaken for
live adapters.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from collections.abc import Iterable, Mapping
from typing import Any

from runtime.platform.event_store.append_contract import AppendEvent, normalize_append_event
from runtime.platform.postgres_port import PostgresPort

CANON_POSTGRES_EVENT_STORE = True
BASE_COLUMNS = (
    "event_id, tenant_id, user_id, source, event_type, timestamp_ms, "
    "decision_id, correlation_id, payload_json"
)
APPEND_COLUMNS = f"append_seq, {BASE_COLUMNS}"
def describe_declared_absence() -> dict[str, object]:
    return {
        "placeholder": True,
        "module": "runtime.platform.event_store.postgres_event_store",
        "canonical_module": "runtime.platform.event_store.postgres_event_store",
        "reason": "driver-backed adapter requires explicit production enablement",
    }
def raise_if_used() -> None:
    raise RuntimeError("POSTGRES_EVENT_STORE_REQUIRES_EXPLICIT_ENABLEMENT")
def _row_to_event(row: tuple[Any, ...]) -> dict[str, Any]:
    has_append_seq = len(row) >= 10
    offset = 1 if has_append_seq else 0
    event = {
        "event_id": row[offset],
        "tenant_id": row[1 + offset],
        "user_id": row[2 + offset],
        "source": row[3 + offset],
        "event_type": row[4 + offset],
        "timestamp_ms": int(row[5 + offset] or 0),
        "decision_id": row[6 + offset],
        "correlation_id": row[7 + offset],
        "payload": json.loads(row[8 + offset] or "{}"),
    }
    if has_append_seq:
        event["append_seq"] = int(row[0])
    return event
def _ensure_psycopg_available() -> None:
    if sys.modules.get("psycopg") is not None:
        return
    if importlib.util.find_spec("psycopg") is None:
        raise RuntimeError("POSTGRES_EVENT_STORE_REQUIRES_PSYCOG_RUNTIME")
def _event_payload_from_kwargs(
    event: Mapping[str, Any] | None,
    **kwargs: Any,
) -> dict[str, Any]:
    payload = dict(event or {})
    for key, value in kwargs.items():
        if value is not None:
            payload[key] = value
    return payload
def _normalized_event_types(
    *,
    event_type: str | None,
    event_types: Iterable[str] | None,
) -> tuple[str, ...]:
    normalized = tuple(
        dict.fromkeys(
            str(item).strip()
            for item in (event_types or ())
            if str(item).strip()
        )
    )
    if normalized:
        return normalized
    singular = str(event_type or "").strip()
    return (singular,) if singular else ()
def _where_clause(
    *,
    tenant_id: str | None,
    start_ms: int | None,
    end_ms: int | None,
    after_append_seq: int | None = None,
    user_id: str | None = None,
    decision_id: str | None = None,
    event_type: str | None = None,
    event_types: Iterable[str] | None = None,
) -> tuple[str, tuple[Any, ...]]:
    clauses: list[str] = []
    params: list[Any] = []
    if tenant_id is not None:
        clauses.append("tenant_id = %s")
        params.append(str(tenant_id))
    if start_ms is not None:
        clauses.append("timestamp_ms >= %s")
        params.append(int(start_ms))
    if end_ms is not None:
        clauses.append("timestamp_ms < %s")
        params.append(int(end_ms))
    if after_append_seq is not None:
        clauses.append("append_seq > %s")
        params.append(max(0, int(after_append_seq)))
    if user_id is not None:
        clauses.append("user_id = %s")
        params.append(str(user_id))
    if decision_id is not None:
        clauses.append("decision_id = %s")
        params.append(str(decision_id))
    types = _normalized_event_types(
        event_type=event_type,
        event_types=event_types,
    )
    if len(types) == 1:
        clauses.append("event_type = %s")
        params.append(types[0])
    elif types:
        placeholders = ",".join("%s" for _ in types)
        clauses.append(f"event_type IN ({placeholders})")
        params.extend(types)
    return (" WHERE " + " AND ".join(clauses) if clauses else "", tuple(params))
class PostgresEventStore:
    def __init__(self, dsn: str, *, enabled: bool = False) -> None:
        self._dsn = str(dsn)
        self._enabled = bool(enabled)
        self._port: PostgresPort | None = None
    def __enter__(self) -> PostgresEventStore:
        if not self._enabled:
            raise_if_used()
        _ensure_psycopg_available()
        self._port = PostgresPort(self._dsn, application_name="businesaios-event-store").__enter__()
        self._init_schema()
        return self
    def __exit__(self, exc_type, exc, tb) -> None:
        if self._port is not None:
            self._port.__exit__(exc_type, exc, tb)
            self._port = None
    @property
    def _db(self) -> PostgresPort:
        if self._port is None:
            raise RuntimeError("postgres event store is not open")
        return self._port
    def _init_schema(self) -> None:
        self._db.execute(
            """
            CREATE TABLE IF NOT EXISTS events (
              append_seq BIGSERIAL UNIQUE,
              event_id TEXT PRIMARY KEY,
              tenant_id TEXT NOT NULL,
              user_id TEXT,
              source TEXT NOT NULL,
              event_type TEXT NOT NULL,
              timestamp_ms BIGINT NOT NULL,
              decision_id TEXT,
              correlation_id TEXT,
              payload_json TEXT NOT NULL
            );
            """
        )
        self._db.execute(
            "ALTER TABLE events ADD COLUMN IF NOT EXISTS append_seq BIGSERIAL;"
        )
        self._db.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_events_append_seq "
            "ON events (append_seq);"
        )
        self._db.execute("CREATE INDEX IF NOT EXISTS idx_events_tenant_ts ON events (tenant_id, timestamp_ms DESC);")
        self._db.execute("CREATE INDEX IF NOT EXISTS idx_events_tenant_type_ts ON events (tenant_id, event_type, timestamp_ms DESC);")
        self._db.execute(
            "CREATE INDEX IF NOT EXISTS idx_events_tenant_append_seq "
            "ON events (tenant_id, append_seq);"
        )
        self._db.execute(
            "CREATE INDEX IF NOT EXISTS idx_events_tenant_decision_type "
            "ON events (tenant_id, decision_id, event_type);"
        )
        self._db.execute("CREATE TABLE IF NOT EXISTS settings (tenant_id TEXT NOT NULL, key TEXT NOT NULL, value_json TEXT NOT NULL, updated_at_ms BIGINT NOT NULL, PRIMARY KEY (tenant_id, key));")
    def append_event(
        self,
        event: Mapping[str, Any] | None = None,
        *,
        commit: bool = True,
        event_type: str | None = None,
        source: str | None = None,
        user_id: str | None = None,
        decision_id: str | None = None,
        correlation_id: str | None = None,
        payload: Mapping[str, Any] | None = None,
        tenant_id: str | None = None,
        timestamp_ms: int | None = None,
        event_id: str | None = None,
    ) -> None:
        normalized: AppendEvent = normalize_append_event(
            _event_payload_from_kwargs(
                event,
                event_type=event_type,
                source=source,
                user_id=user_id,
                decision_id=decision_id,
                correlation_id=correlation_id,
                payload=dict(payload) if payload is not None else None,
                tenant_id=tenant_id,
                timestamp_ms=timestamp_ms,
                event_id=event_id,
            )
        )
        self._db.execute(
            "SELECT pg_advisory_xact_lock(hashtext(%s));",
            (f"event-append:{normalized.tenant_id}",),
        )
        self._db.execute(
            """
            INSERT INTO events (
              event_id, tenant_id, user_id, source, event_type, timestamp_ms,
              decision_id, correlation_id, payload_json
            ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
            ON CONFLICT (event_id) DO NOTHING;
            """,
            (
                normalized.event_id,
                normalized.tenant_id,
                normalized.user_id,
                normalized.source,
                normalized.event_type,
                normalized.timestamp_ms,
                normalized.decision_id,
                normalized.correlation_id,
                json.dumps(normalized.payload, ensure_ascii=False, sort_keys=True),
            ),
        )
        if commit:
            self._db.commit()
    def latest_append_seq(self, *, tenant_id: str) -> int:
        row = self._db.fetchone(
            "SELECT COALESCE(MAX(append_seq), 0) FROM events "
            "WHERE tenant_id = %s;",
            (str(tenant_id),),
        )
        return int(row[0] or 0) if row else 0
    def iter_events(
        self,
        *,
        tenant_id: str,
        start_ms: int = 0,
        end_ms: int | None = None,
        after_append_seq: int | None = None,
        user_id: str | None = None,
        decision_id: str | None = None,
        event_type: str | None = None,
        event_types: Iterable[str] | None = None,
        limit: int | None = None,
    ) -> Iterable[dict[str, Any]]:
        where, params = _where_clause(
            tenant_id=tenant_id,
            start_ms=start_ms,
            end_ms=end_ms,
            after_append_seq=after_append_seq,
            user_id=user_id,
            decision_id=decision_id,
            event_type=event_type,
            event_types=event_types,
        )
        limit_sql = ""
        query_params = list(params)
        if limit is not None:
            limit_sql = " LIMIT %s"
            query_params.append(max(1, int(limit)))
        include_append_seq = after_append_seq is not None
        order_by = (
            "append_seq ASC"
            if include_append_seq
            else "timestamp_ms ASC, event_id ASC"
        )
        columns = APPEND_COLUMNS if include_append_seq else BASE_COLUMNS
        rows = self._db.fetchall(
            f"SELECT {columns} FROM events{where} "
            f"ORDER BY {order_by}{limit_sql};",
            tuple(query_params),
        )
        for row in rows:
            yield _row_to_event(tuple(row))
    def count_events(
        self,
        *,
        tenant_id: str,
        start_ms: int = 0,
        end_ms: int | None = None,
        user_id: str | None = None,
        event_type: str | None = None,
    ) -> int:
        where, params = _where_clause(
            tenant_id=tenant_id,
            start_ms=start_ms,
            end_ms=end_ms,
            user_id=user_id,
            event_type=event_type,
        )
        row = self._db.fetchone(f"SELECT COUNT(*) FROM events{where};", params)
        return int(row[0] if row else 0)
    def query_events(
        self,
        *,
        tenant_id: str | None = None,
        event_type: str | None = None,
        event_types: Iterable[str] | None = None,
        user_id: str | None = None,
        decision_id: str | None = None,
        start_ms: int | None = None,
        end_ms: int | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        where, params = _where_clause(
            tenant_id=tenant_id,
            start_ms=start_ms,
            end_ms=end_ms,
            user_id=user_id,
            decision_id=decision_id,
            event_type=event_type,
            event_types=event_types,
        )
        bounded_limit = max(1, int(limit))
        rows = self._db.fetchall(
            f"SELECT {BASE_COLUMNS} FROM events{where} "
            "ORDER BY timestamp_ms DESC, event_id DESC LIMIT %s;",
            (*params, bounded_limit),
        )
        return [_row_to_event(tuple(row)) for row in rows]
    def latest_events(
        self,
        *,
        tenant_id: str | None = None,
        user_id: str | None = None,
        event_type: str | None = None,
        event_types: Iterable[str] | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        return self.query_events(
            tenant_id=tenant_id,
            user_id=user_id,
            event_type=event_type,
            event_types=event_types,
            limit=limit,
        )
    def latest_event(
        self,
        *,
        tenant_id: str | None = None,
        user_id: str | None = None,
        event_type: str | None = None,
        event_types: Iterable[str] | None = None,
    ) -> dict[str, Any] | None:
        events = self.latest_events(
            tenant_id=tenant_id,
            user_id=user_id,
            event_type=event_type,
            event_types=event_types,
            limit=1,
        )
        return events[0] if events else None
    def get_setting(self, *, tenant_id: str, key: str):
        row = self._db.fetchone("SELECT value_json FROM settings WHERE tenant_id=%s AND key=%s", (str(tenant_id), str(key)))
        if not row:
            return None
        try:
            return json.loads(str(row[0] or "{}"))
        except Exception:
            return None
    def set_setting(self, *, tenant_id: str, key: str, value) -> None:
        import time
        self._db.execute("INSERT INTO settings(tenant_id,key,value_json,updated_at_ms) VALUES (%s,%s,%s,%s) ON CONFLICT(tenant_id,key) DO UPDATE SET value_json=excluded.value_json, updated_at_ms=excluded.updated_at_ms", (str(tenant_id), str(key), json.dumps(value, ensure_ascii=False, sort_keys=True), int(time.time() * 1000)))
        self._db.commit()
    def compare_and_set_setting(self, *, tenant_id: str, key: str, expected, value) -> bool:
        import time
        encoded, now = json.dumps(value, ensure_ascii=False, sort_keys=True), int(time.time() * 1000)
        if expected is None:
            row = self._db.fetchone("INSERT INTO settings(tenant_id,key,value_json,updated_at_ms) VALUES (%s,%s,%s,%s) ON CONFLICT(tenant_id,key) DO NOTHING RETURNING 1", (str(tenant_id), str(key), encoded, now))
        else:
            row = self._db.fetchone("UPDATE settings SET value_json=%s, updated_at_ms=%s WHERE tenant_id=%s AND key=%s AND value_json=%s RETURNING 1", (encoded, now, str(tenant_id), str(key), json.dumps(expected, ensure_ascii=False, sort_keys=True)))
        self._db.commit()
        return bool(row)
    def ping(self) -> bool:
        return self._db.ping()
    def healthcheck(self) -> dict[str, Any]:
        ok = self.ping()
        return {
            "surface": "runtime.platform.event_store.postgres_event_store",
            "canonical_owner": "runtime.platform.event_store.postgres_event_store",
            "storage_only": True,
            "decision_logic": False,
            "ok": ok,
        }
__all__ = [
    "CANON_POSTGRES_EVENT_STORE",
    "PostgresEventStore",
    "describe_declared_absence",
    "raise_if_used",
]

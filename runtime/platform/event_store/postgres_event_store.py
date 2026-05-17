from __future__ import annotations

"""Canonical Postgres event-store adapter.

The driver remains sealed behind runtime.platform.postgres_port.PostgresPort.
This adapter mirrors the canonical sqlite event-store append/query semantics used
by runtime boot: append durable events, query governance readers, query latest
events, count events, and provide a health probe. It intentionally keeps
explicit production enablement so capability surfaces cannot be mistaken for
live adapters.
"""

import importlib.util
import json
import sys
from typing import Any, Iterable, Mapping

from runtime.platform.event_store.append_contract import AppendEvent, normalize_append_event
from runtime.platform.postgres_port import PostgresPort

CANON_POSTGRES_EVENT_STORE = True


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
    return {
        "event_id": row[0],
        "tenant_id": row[1],
        "user_id": row[2],
        "source": row[3],
        "event_type": row[4],
        "timestamp_ms": int(row[5] or 0),
        "decision_id": row[6],
        "correlation_id": row[7],
        "payload": json.loads(row[8] or "{}"),
    }


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


def _where_clause(
    *,
    tenant_id: str | None,
    start_ms: int | None,
    end_ms: int | None,
    user_id: str | None,
    event_type: str | None,
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
    if user_id is not None:
        clauses.append("user_id = %s")
        params.append(str(user_id))
    if event_type is not None:
        clauses.append("event_type = %s")
        params.append(str(event_type))
    return (" WHERE " + " AND ".join(clauses) if clauses else "", tuple(params))


class PostgresEventStore:
    def __init__(self, dsn: str, *, enabled: bool = False) -> None:
        self._dsn = str(dsn)
        self._enabled = bool(enabled)
        self._port: PostgresPort | None = None

    def __enter__(self) -> "PostgresEventStore":
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
        self._db.execute("CREATE INDEX IF NOT EXISTS idx_events_tenant_ts ON events (tenant_id, timestamp_ms DESC);")
        self._db.execute("CREATE INDEX IF NOT EXISTS idx_events_tenant_type_ts ON events (tenant_id, event_type, timestamp_ms DESC);")

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

    def iter_events(
        self,
        *,
        tenant_id: str,
        start_ms: int = 0,
        end_ms: int | None = None,
        user_id: str | None = None,
        event_type: str | None = None,
    ) -> Iterable[dict[str, Any]]:
        where, params = _where_clause(
            tenant_id=tenant_id,
            start_ms=start_ms,
            end_ms=end_ms,
            user_id=user_id,
            event_type=event_type,
        )
        rows = self._db.fetchall(
            f"""
            SELECT event_id, tenant_id, user_id, source, event_type, timestamp_ms,
                   decision_id, correlation_id, payload_json
            FROM events{where}
            ORDER BY timestamp_ms ASC, event_id ASC;
            """,
            params,
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
        user_id: str | None = None,
        start_ms: int | None = None,
        end_ms: int | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        where, params = _where_clause(
            tenant_id=tenant_id,
            start_ms=start_ms,
            end_ms=end_ms,
            user_id=user_id,
            event_type=event_type,
        )
        bounded_limit = max(1, int(limit))
        rows = self._db.fetchall(
            f"""
            SELECT event_id, tenant_id, user_id, source, event_type, timestamp_ms,
                   decision_id, correlation_id, payload_json
            FROM events{where}
            ORDER BY timestamp_ms DESC, event_id DESC
            LIMIT %s;
            """,
            (*params, bounded_limit),
        )
        return [_row_to_event(tuple(row)) for row in rows]

    def latest_events(
        self,
        *,
        tenant_id: str | None = None,
        user_id: str | None = None,
        event_type: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        return self.query_events(
            tenant_id=tenant_id,
            user_id=user_id,
            event_type=event_type,
            limit=limit,
        )

    def latest_event(
        self,
        *,
        tenant_id: str | None = None,
        user_id: str | None = None,
        event_type: str | None = None,
    ) -> dict[str, Any] | None:
        events = self.latest_events(
            tenant_id=tenant_id,
            user_id=user_id,
            event_type=event_type,
            limit=1,
        )
        return events[0] if events else None

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

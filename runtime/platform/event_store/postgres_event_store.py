from __future__ import annotations

"""Canonical Postgres event-store adapter.

The driver remains sealed behind runtime.platform.postgres_port.PostgresPort.
This adapter mirrors the canonical sqlite event-store append/query semantics used
by runtime boot: append durable events, query governance readers, query latest
events, and provide a health probe. It intentionally keeps explicit production
enablement so capability surfaces cannot be mistaken for live adapters.
"""

import importlib.util
import json
from typing import Any, Iterable, Mapping

from runtime.platform.event_store.append_contract import normalize_append_event
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
    if importlib.util.find_spec("psycopg") is None:
        raise RuntimeError("POSTGRES_EVENT_STORE_REQUIRES_PSYCOG_RUNTIME")


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

    def append_event(
        self,
        *,
        event_type: str,
        source: str,
        user_id: str = "",
        decision_id: str = "",
        correlation_id: str = "",
        payload: Mapping[str, Any] | None = None,
        tenant_id: str | None = None,
        timestamp_ms: int | None = None,
        event_id: str | None = None,
    ) -> dict[str, Any]:
        normalized = normalize_append_event(
            event_type=event_type,
            source=source,
            user_id=user_id,
            decision_id=decision_id,
            correlation_id=correlation_id,
            payload=payload,
            tenant_id=tenant_id,
            timestamp_ms=timestamp_ms,
            event_id=event_id,
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
                normalized["event_id"],
                normalized["tenant_id"],
                normalized["user_id"],
                normalized["source"],
                normalized["event_type"],
                normalized["timestamp_ms"],
                normalized["decision_id"],
                normalized["correlation_id"],
                json.dumps(normalized["payload"], ensure_ascii=False, sort_keys=True),
            ),
        )
        return normalized

    def query_events(
        self,
        *,
        tenant_id: str | None = None,
        event_type: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        clauses: list[str] = []
        params: list[Any] = []
        if tenant_id is not None:
            clauses.append("tenant_id = %s")
            params.append(str(tenant_id))
        if event_type is not None:
            clauses.append("event_type = %s")
            params.append(str(event_type))
        where = " WHERE " + " AND ".join(clauses) if clauses else ""
        params.append(max(1, int(limit)))
        rows = self._db.fetchall(
            f"""
            SELECT event_id, tenant_id, user_id, source, event_type, timestamp_ms,
                   decision_id, correlation_id, payload_json
            FROM events{where}
            ORDER BY timestamp_ms DESC, event_id DESC
            LIMIT %s;
            """,
            tuple(params),
        )
        return [_row_to_event(tuple(row)) for row in rows]

    def latest_events(self, *, limit: int = 100) -> list[dict[str, Any]]:
        return self.query_events(limit=limit)

    def healthcheck(self) -> dict[str, Any]:
        row = self._db.fetchone("SELECT 1;")
        return {
            "surface": "runtime.platform.event_store.postgres_event_store",
            "canonical_owner": "runtime.platform.event_store.postgres_event_store",
            "storage_only": True,
            "decision_logic": False,
            "ok": bool(row),
        }


__all__ = [
    "CANON_POSTGRES_EVENT_STORE",
    "PostgresEventStore",
    "describe_declared_absence",
    "raise_if_used",
]

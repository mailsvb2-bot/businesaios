from __future__ import annotations

"""Canonical Postgres event-store adapter.

The driver remains sealed behind runtime.platform.postgres_port.PostgresPort.
This adapter mirrors the sqlite event-store semantics used by runtime boot:
append durable events, query latest events, and provide a health probe.
"""

import json
from typing import Any, Mapping

from runtime.platform.postgres_port import PostgresPort

CANON_POSTGRES_EVENT_STORE = True


def describe_declared_absence() -> dict[str, object]:
    return {
        "placeholder": True,
        "module": "runtime.platform.event_store.postgres_event_store",
        "canonical_module": "runtime.platform.event_store.postgres_event_store",
        "reason": "driver-backed adapter requires psycopg at runtime",
    }


def raise_if_used() -> None:
    raise RuntimeError("POSTGRES_EVENT_STORE_REQUIRES_PSYCOG_RUNTIME")


class PostgresEventStore:
    def __init__(self, dsn: str) -> None:
        self._dsn = str(dsn)
        self._port: PostgresPort | None = None

    def __enter__(self) -> "PostgresEventStore":
        try:
            __import__("psycopg")
        except Exception as exc:
            raise RuntimeError("POSTGRES_EVENT_STORE_REQUIRES_PSYCOG_RUNTIME") from exc
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
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              tenant_id TEXT NOT NULL,
              user_id TEXT NOT NULL,
              source TEXT NOT NULL,
              event_type TEXT NOT NULL,
              timestamp_ms BIGINT NOT NULL,
              decision_id TEXT,
              correlation_id TEXT,
              payload_json TEXT NOT NULL
            );
            """
        )
        self._db.execute("CREATE INDEX IF NOT EXISTS idx_events_tenant_user_time ON events(tenant_id, user_id, timestamp_ms);")
        self._db.execute("CREATE INDEX IF NOT EXISTS idx_events_decision_id ON events(decision_id);")
        self._db.commit()

    def ping(self) -> bool:
        return self._db.ping()

    def append_event(self, event: Mapping[str, Any]) -> None:
        payload = dict(event.get("payload") or {})
        self._db.execute(
            """
            INSERT INTO events(tenant_id, user_id, source, event_type, timestamp_ms, decision_id, correlation_id, payload_json)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s);
            """,
            (
                str(event.get("tenant_id") or "global"),
                str(event.get("user_id") or ""),
                str(event.get("source") or "runtime"),
                str(event.get("event_type") or "event"),
                int(event.get("timestamp_ms") or 0),
                event.get("decision_id"),
                event.get("correlation_id"),
                json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")),
            ),
        )
        self._db.commit()

    def latest_event(self, *, tenant_id: str, user_id: str) -> dict[str, Any] | None:
        row = self._db.fetchone(
            """
            SELECT tenant_id, user_id, source, event_type, timestamp_ms, decision_id, correlation_id, payload_json
            FROM events WHERE tenant_id=%s AND user_id=%s ORDER BY timestamp_ms DESC, id DESC LIMIT 1;
            """,
            (str(tenant_id), str(user_id)),
        )
        if not row:
            return None
        return {
            "tenant_id": row[0],
            "user_id": row[1],
            "source": row[2],
            "event_type": row[3],
            "timestamp_ms": int(row[4] or 0),
            "decision_id": row[5],
            "correlation_id": row[6],
            "payload": json.loads(row[7] or "{}"),
        }


__all__ = ["CANON_POSTGRES_EVENT_STORE", "PostgresEventStore", "describe_declared_absence", "raise_if_used"]

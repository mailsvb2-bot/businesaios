from __future__ import annotations

"""Canonical Postgres event-store adapter.

The driver remains sealed behind runtime.platform.postgres_port.PostgresPort.
This adapter mirrors the canonical sqlite event-store append semantics used by
runtime boot: append durable events, query latest events, and provide a health
probe. It intentionally keeps explicit production enablement so capability
surfaces cannot be mistaken for live adapters.
"""

import json
from typing import Any, Mapping

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


class PostgresEventStore:
    def __init__(self, dsn: str, *, enabled: bool = False) -> None:
        self._dsn = str(dsn)
        self._enabled = bool(enabled)
        self._port: PostgresPort | None = None

    def __enter__(self) -> "PostgresEventStore":
        if not self._enabled:
            raise_if_used()
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
        self._db.execute("CREATE INDEX IF NOT EXISTS idx_events_ts ON events(timestamp_ms);")
        self._db.execute("CREATE INDEX IF NOT EXISTS idx_events_type_ts ON events(event_type, timestamp_ms);")
        self._db.execute("CREATE INDEX IF NOT EXISTS idx_events_user_ts ON events(user_id, timestamp_ms);")
        self._db.execute("CREATE INDEX IF NOT EXISTS idx_events_type_user_ts ON events(event_type, user_id, timestamp_ms);")
        self._db.execute("CREATE INDEX IF NOT EXISTS idx_events_tenant_user_ts ON events(tenant_id, user_id, timestamp_ms);")
        self._db.execute("CREATE INDEX IF NOT EXISTS idx_events_tenant_type_ts ON events(tenant_id, event_type, timestamp_ms);")
        self._db.execute("CREATE INDEX IF NOT EXISTS idx_events_decision_id ON events(decision_id);")
        self._db.commit()

    def ping(self) -> bool:
        return self._db.ping()

    def append_event(self, event: Mapping[str, Any], *, commit: bool = True) -> None:
        append = normalize_append_event(dict(event or {}))
        self._db.execute(
            """
            INSERT INTO events(
              event_id, tenant_id, user_id, source, event_type, timestamp_ms,
              decision_id, correlation_id, payload_json
            ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s);
            """,
            (
                append.event_id,
                append.tenant_id,
                append.user_id,
                append.source,
                append.event_type,
                append.timestamp_ms,
                append.decision_id,
                append.correlation_id,
                json.dumps(append.payload, ensure_ascii=False, sort_keys=True),
            ),
        )
        if commit:
            self._db.commit()

    def latest_event(
        self,
        *,
        tenant_id: str = "default",
        user_id: Any = None,
        event_types: list[str] | tuple[str, ...] | set[str] | None = None,
    ) -> dict[str, Any] | None:
        params: list[Any] = [str(tenant_id)]
        where = ["tenant_id=%s"]
        if user_id is not None:
            where.append("user_id=%s")
            params.append(user_id)
        if event_types:
            event_type_values = [str(v) for v in event_types]
            placeholders = ",".join(["%s"] * len(event_type_values))
            where.append(f"event_type IN ({placeholders})")
            params.extend(event_type_values)
        row = self._db.fetchone(
            "SELECT event_id, tenant_id, user_id, source, event_type, timestamp_ms, decision_id, correlation_id, payload_json "
            f"FROM events WHERE {' AND '.join(where)} ORDER BY timestamp_ms DESC, event_id DESC LIMIT 1;",
            tuple(params),
        )
        if not row:
            return None
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


__all__ = ["CANON_POSTGRES_EVENT_STORE", "PostgresEventStore", "describe_declared_absence", "raise_if_used"]

"""PostgreSQL backend for the client-outcome JSON registries (orders, ...).

Same contract as ``SQLiteJsonRegistryBackend`` (replace / compare_and_replace /
register_unique / get / maybe_get / items) so ``OrderStore`` and every other
registry owner stay unchanged. Opt-in via
``BUSINESAIOS_CLIENT_OUTCOME_BACKEND=postgres`` + ``POSTGRES_DSN``; payloads are
stored as canonical JSON text so compare-and-replace keeps byte semantics.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import Any

from runtime.platform.client_outcome_sqlite_core import _json_dumps, _json_loads
from runtime.platform.postgres_port import PostgresPort

CANON_CLIENT_OUTCOME_POSTGRES_PERSISTENCE = True

DDL = """
CREATE TABLE IF NOT EXISTS client_outcome_registry (
    namespace TEXT NOT NULL,
    item_key TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    updated_at_epoch_ms BIGINT NOT NULL,
    PRIMARY KEY(namespace, item_key)
);
"""


class PostgresJsonRegistryBackend:
    def __init__(self, *, namespace: str, dsn: str = "", port_factory: Callable[[], Any] | None = None) -> None:
        self._namespace = str(namespace).strip()
        if not self._namespace:
            raise ValueError("namespace is required")
        if port_factory is None and not str(dsn).strip():
            raise ValueError("POSTGRES_DSN is required for the postgres client-outcome backend")
        self._factory = port_factory or (lambda: PostgresPort(dsn=dsn, application_name="businesaios-client-outcome"))
        self._schema_ready = False

    def _tx(self, fn: Callable[[Any], Any]) -> Any:
        with self._factory() as port, port.transaction():
            if not self._schema_ready:
                port.execute(DDL)
                self._schema_ready = True
            return fn(port)

    @staticmethod
    def _key(key: str) -> str:
        normalized = str(key).strip()
        if not normalized:
            raise ValueError("registry key is required")
        return normalized

    def replace(self, key: str, value: object) -> None:
        args = (self._namespace, self._key(key), _json_dumps(value), int(time.time() * 1000))
        self._tx(lambda p: p.execute(
            "INSERT INTO client_outcome_registry(namespace, item_key, payload_json, updated_at_epoch_ms) "
            "VALUES (%s, %s, %s, %s) ON CONFLICT (namespace, item_key) DO UPDATE SET "
            "payload_json=EXCLUDED.payload_json, updated_at_epoch_ms=EXCLUDED.updated_at_epoch_ms", args))

    def compare_and_replace(self, key: str, expected: object, value: object) -> bool:
        args = (_json_dumps(value), int(time.time() * 1000), self._namespace, self._key(key), _json_dumps(expected))
        row = self._tx(lambda p: p.fetchone(
            "UPDATE client_outcome_registry SET payload_json=%s, updated_at_epoch_ms=%s "
            "WHERE namespace=%s AND item_key=%s AND payload_json=%s RETURNING item_key", args))
        return row is not None

    def register_unique(self, key: str, value: object) -> None:
        normalized = self._key(key)
        args = (self._namespace, normalized, _json_dumps(value), int(time.time() * 1000))
        row = self._tx(lambda p: p.fetchone(
            "INSERT INTO client_outcome_registry(namespace, item_key, payload_json, updated_at_epoch_ms) "
            "VALUES (%s, %s, %s, %s) ON CONFLICT DO NOTHING RETURNING item_key", args))
        if row is None:
            raise ValueError(f"duplicate registry key: {normalized}")

    def get(self, key: str) -> object:
        normalized = str(key).strip()
        row = self._tx(lambda p: p.fetchone(
            "SELECT payload_json FROM client_outcome_registry WHERE namespace=%s AND item_key=%s",
            (self._namespace, normalized)))
        if row is None:
            raise KeyError(normalized)
        return _json_loads(str(row[0]))

    def maybe_get(self, key: str) -> object | None:
        try:
            return self.get(key)
        except KeyError:
            return None

    def items(self) -> tuple[tuple[str, object], ...]:
        rows = self._tx(lambda p: p.fetchall(
            "SELECT item_key, payload_json FROM client_outcome_registry WHERE namespace=%s ORDER BY item_key",
            (self._namespace,)))
        return tuple((str(k), _json_loads(str(v))) for k, v in rows)


__all__ = ["CANON_CLIENT_OUTCOME_POSTGRES_PERSISTENCE", "DDL", "PostgresJsonRegistryBackend"]

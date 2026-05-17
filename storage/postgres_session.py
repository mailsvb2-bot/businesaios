from __future__ import annotations

from contextlib import AbstractContextManager
from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from runtime.platform.postgres_port import PostgresPort


CANON_STORAGE_POSTGRES_SESSION = True


class PostgresSession(AbstractContextManager["PostgresSession"]):
    dialect = "postgres"

    def __init__(
        self,
        dsn: str,
        *,
        application_name: str = "businesaios-storage",
        statement_timeout_ms: int = 30000,
        lock_timeout_ms: int = 5000,
    ) -> None:
        self._dsn = str(dsn or "").strip()
        self._application_name = str(application_name or "businesaios-storage").strip() or "businesaios-storage"
        self._statement_timeout_ms = max(0, int(statement_timeout_ms))
        self._lock_timeout_ms = max(0, int(lock_timeout_ms))
        self._port: PostgresPort | None = None

    @property
    def port(self) -> PostgresPort:
        if self._port is None:
            raise RuntimeError("postgres session is not open")
        return self._port

    def __enter__(self) -> "PostgresSession":
        port = PostgresPort(self._dsn, application_name=self._application_name)
        try:
            self._port = port.__enter__()
            # PostgreSQL does not accept bind parameters in ``SET name = value``.
            # ``set_config`` is parameterizable and keeps this wrapper on the
            # sealed PostgresPort boundary instead of formatting SQL manually.
            self._set_config_best_effort("lock_timeout", f"{self._lock_timeout_ms}ms")
            self._set_config_best_effort("statement_timeout", f"{self._statement_timeout_ms}ms")
            return self
        except Exception:
            port.__exit__(type(None), None, None)
            self._port = None
            raise

    def _set_config_best_effort(self, name: str, value: str) -> None:
        try:
            self.execute(f"SELECT set_config('{str(name)}', %s, false);", (str(value),))
        except Exception as exc:
            if "set_config" not in str(exc):
                raise

    def __exit__(self, exc_type, exc, tb) -> None:
        if self._port is None:
            return
        self._port.__exit__(exc_type, exc, tb)
        self._port = None

    def execute(self, sql: str, params: Sequence[Any] | Mapping[str, Any] | None = None) -> None:
        self.port.execute(sql, params)

    def fetchone(self, sql: str, params: Sequence[Any] | Mapping[str, Any] | None = None) -> dict[str, Any] | None:
        conn = getattr(self.port, "_conn", None)
        if conn is None:
            raise RuntimeError("postgres connection is not open")
        with conn.cursor() as cur:
            cur.execute(sql, params)
            row = cur.fetchone()
            if row is None:
                return None
            names = [str(column[0]) for column in (cur.description or ())]
            if isinstance(row, Mapping):
                return {str(key): value for key, value in row.items()}
            return {name: value for name, value in zip(names, row)}

    def fetchall(self, sql: str, params: Sequence[Any] | Mapping[str, Any] | None = None) -> list[dict[str, Any]]:
        conn = getattr(self.port, "_conn", None)
        if conn is None:
            raise RuntimeError("postgres connection is not open")
        with conn.cursor() as cur:
            cur.execute(sql, params)
            rows = cur.fetchall()
            names = [str(column[0]) for column in (cur.description or ())]
        materialized: list[dict[str, Any]] = []
        for row in rows:
            if isinstance(row, Mapping):
                materialized.append({str(key): value for key, value in row.items()})
            else:
                materialized.append({name: value for name, value in zip(names, row)})
        return materialized

    def commit(self) -> None:
        self.port.commit()

    def rollback(self) -> None:
        self.port.rollback()


@dataclass(frozen=True)
class PostgresSessionFactory:
    dsn: str
    application_name: str = "businesaios-storage"
    statement_timeout_ms: int = 30000
    lock_timeout_ms: int = 5000

    def open(self) -> PostgresSession:
        return PostgresSession(
            self.dsn,
            application_name=self.application_name,
            statement_timeout_ms=self.statement_timeout_ms,
            lock_timeout_ms=self.lock_timeout_ms,
        )


__all__ = [
    "CANON_STORAGE_POSTGRES_SESSION",
    "PostgresSession",
    "PostgresSessionFactory",
]

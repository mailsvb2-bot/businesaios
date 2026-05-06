from __future__ import annotations

"""PostgresPort — the only place where the real DB driver is imported.

We treat database drivers as external integrations and keep their imports sealed
inside runtime.platform. Platform stores may *use* this port, but must not import
psycopg (or any other driver) directly.

This keeps the dependency surface narrow and auditable.
"""

from dataclasses import dataclass
from typing import Any, Mapping, Sequence


@dataclass
class PostgresPort:
    dsn: str
    application_name: str = "businesaios"

    def __post_init__(self) -> None:
        if not self.dsn or not str(self.dsn).strip():
            raise ValueError("POSTGRES_DSN is empty")

    def __enter__(self) -> "PostgresPort":
        import psycopg  # type: ignore

        self._psycopg = psycopg
        self._conn = psycopg.connect(self.dsn, autocommit=False)
        try:
            with self._conn.cursor() as cur:
                cur.execute("SET application_name = %s;", (self.application_name,))
            self._conn.commit()
        except Exception:
            self._conn.rollback()
            raise
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        if getattr(self, "_conn", None) is None:
            return
        try:
            if exc_type is None:
                self._conn.commit()
            else:
                self._conn.rollback()
        finally:
            self._conn.close()

    def execute(self, sql: str, params: Sequence[Any] | Mapping[str, Any] | None = None) -> None:
        with self._conn.cursor() as cur:
            cur.execute(sql, params)

    def fetchone(self, sql: str, params: Sequence[Any] | Mapping[str, Any] | None = None):
        with self._conn.cursor() as cur:
            cur.execute(sql, params)
            return cur.fetchone()

    def fetchall(self, sql: str, params: Sequence[Any] | Mapping[str, Any] | None = None):
        with self._conn.cursor() as cur:
            cur.execute(sql, params)
            return cur.fetchall()

    def ping(self) -> bool:
        try:
            self.fetchone("SELECT 1;")
            return True
        except Exception:
            return False

    def commit(self) -> None:
        self._conn.commit()

    def rollback(self) -> None:
        self._conn.rollback()

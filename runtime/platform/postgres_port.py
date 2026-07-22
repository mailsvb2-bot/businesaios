"""PostgresPort — the only place where the real DB driver is imported.

We treat database drivers as external integrations and keep their imports sealed
inside runtime.platform. Platform stores may *use* this port, but must not import
psycopg (or any other driver) directly.

This keeps the dependency surface narrow and auditable.
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any


@dataclass
class PostgresPort:
    dsn: str
    application_name: str = "businesaios"

    def __post_init__(self) -> None:
        if not self.dsn or not str(self.dsn).strip():
            raise ValueError("POSTGRES_DSN is empty")

    def __enter__(self) -> PostgresPort:
        import psycopg  # type: ignore

        self._psycopg = psycopg
        self._conn = psycopg.connect(self.dsn, autocommit=False)
        try:
            with self._conn.cursor() as cur:
                # PostgreSQL does not accept bind parameters in ``SET name = value``.
                # ``set_config`` is parameterizable and keeps the driver boundary sealed.
                try:
                    cur.execute(
                        "SELECT set_config('application_name', %s, false);",
                        (self.application_name,),
                    )
                except Exception as exc:
                    if "set_config" not in str(exc):
                        raise
                    # A failed statement aborts the current PostgreSQL transaction.
                    # The compatibility path must clear that state before the store is used.
                    self._conn.rollback()
                    return self
            self._conn.commit()
        except Exception as exc:
            try:
                self._conn.rollback()
            except Exception as rollback_exc:
                exc.add_note(f"PostgreSQL rollback also failed: {rollback_exc}")
            try:
                self._conn.close()
            except Exception as close_exc:
                exc.add_note(f"PostgreSQL close also failed: {close_exc}")
            finally:
                self._conn = None
            raise
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        conn = getattr(self, "_conn", None)
        if conn is None:
            return

        operation_error: Exception | None = None
        try:
            if exc_type is None:
                try:
                    conn.commit()
                except Exception as commit_exc:
                    operation_error = commit_exc
                    try:
                        conn.rollback()
                    except Exception as rollback_exc:
                        commit_exc.add_note(f"PostgreSQL rollback also failed: {rollback_exc}")
            else:
                try:
                    conn.rollback()
                except Exception as rollback_exc:
                    if exc is not None:
                        exc.add_note(f"PostgreSQL rollback also failed: {rollback_exc}")
                    else:
                        operation_error = rollback_exc
        finally:
            try:
                conn.close()
            except Exception as close_exc:
                primary = exc if exc is not None else operation_error
                if primary is not None:
                    primary.add_note(f"PostgreSQL close also failed: {close_exc}")
                else:
                    operation_error = close_exc
            finally:
                self._conn = None

        if operation_error is not None:
            raise operation_error

    @contextmanager
    def transaction(self) -> Iterator[PostgresPort]:
        """Own one explicit database transaction inside the sealed driver port."""
        try:
            yield self
        except Exception as exc:
            try:
                self.rollback()
            except Exception as rollback_exc:
                exc.add_note(f"PostgreSQL rollback also failed: {rollback_exc}")
            raise
        else:
            try:
                self.commit()
            except Exception as exc:
                try:
                    self.rollback()
                except Exception as rollback_exc:
                    exc.add_note(f"PostgreSQL rollback also failed: {rollback_exc}")
                raise

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

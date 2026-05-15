from __future__ import annotations

import sqlite3
from contextlib import AbstractContextManager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Sequence


CANON_STORAGE_SQLITE_FALLBACK = True


class SqliteSession(AbstractContextManager["SqliteSession"]):
    dialect = "sqlite"

    def __init__(
        self,
        path: str | Path,
        *,
        wal: bool = True,
        busy_timeout_ms: int = 5000,
        synchronous: str = "NORMAL",
    ) -> None:
        self._path = Path(path)
        self._wal = bool(wal)
        self._busy_timeout_ms = max(0, int(busy_timeout_ms))
        self._synchronous = str(synchronous or "NORMAL").upper()
        self._conn: Any | None = None

    @property
    def path(self) -> Path:
        return self._path

    @property
    def connection(self) -> Any:
        if self._conn is None:
            raise RuntimeError("sqlite session is not open")
        return self._conn

    def __enter__(self) -> "SqliteSession":
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self._path))
        self._conn.row_factory = sqlite3.Row
        self._configure(self._conn)
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        if self._conn is None:
            return
        try:
            if exc_type is None:
                self._conn.commit()
            else:
                self._conn.rollback()
        finally:
            self._conn.close()
            self._conn = None

    def _configure(self, conn: Any) -> None:
        if self._wal:
            conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute(f"PRAGMA synchronous={self._synchronous};")
        conn.execute("PRAGMA foreign_keys=ON;")
        conn.execute("PRAGMA temp_store=MEMORY;")
        conn.execute(f"PRAGMA busy_timeout={self._busy_timeout_ms};")

    def execute(self, sql: str, params: Sequence[Any] | None = None) -> Any:
        return self.connection.execute(sql, tuple(params or ()))

    def executemany(self, sql: str, rows: Iterable[Sequence[Any]]) -> Any:
        return self.connection.executemany(sql, list(rows))

    def fetchall(self, sql: str, params: Sequence[Any] | None = None) -> list[Any]:
        return list(self.execute(sql, params).fetchall())

    def fetchone(self, sql: str, params: Sequence[Any] | None = None) -> Any | None:
        return self.execute(sql, params).fetchone()


@dataclass(frozen=True)
class SqliteSessionFactory:
    path: str | Path
    wal: bool = True
    busy_timeout_ms: int = 5000
    synchronous: str = "NORMAL"

    def open(self) -> SqliteSession:
        return SqliteSession(
            self.path,
            wal=self.wal,
            busy_timeout_ms=self.busy_timeout_ms,
            synchronous=self.synchronous,
        )

    def __call__(self) -> SqliteSession:
        return self.open()


__all__ = ["CANON_STORAGE_SQLITE_FALLBACK", "SqliteSession", "SqliteSessionFactory"]

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

CANON_PLATFORM_SECURITY_SQLITE_STORES = True


def _ensure_parent(db_path: str) -> None:
    Path(str(db_path)).parent.mkdir(parents=True, exist_ok=True)


def open_security_sqlite_connection(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    return conn


def _connect(db_path: str) -> Any:
    return open_security_sqlite_connection(str(db_path))


__all__ = [
    "CANON_PLATFORM_SECURITY_SQLITE_STORES",
    "_connect",
    "_ensure_parent",
    "open_security_sqlite_connection",
]

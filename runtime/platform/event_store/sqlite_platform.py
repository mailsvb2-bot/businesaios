"""Canonical sqlite platform shim.

This module centralizes stdlib sqlite imports inside the approved runtime.platform
storage zone so domain packages can depend on a typed storage adapter instead of
opening direct sqlite side channels.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

CANON_RUNTIME_PLATFORM_SQLITE_PLATFORM = True

SQLiteConnection = sqlite3.Connection
SQLiteRow = sqlite3.Row
SQLITE_ROW_FACTORY = sqlite3.Row


def connect_sqlite(path: str | Path, *, timeout: float = 30.0, isolation_level: str | None = None) -> SQLiteConnection:
    return sqlite3.connect(str(path), timeout=float(timeout), isolation_level=isolation_level)


__all__ = [
    "CANON_RUNTIME_PLATFORM_SQLITE_PLATFORM",
    "SQLITE_ROW_FACTORY",
    "SQLiteConnection",
    "SQLiteRow",
    "connect_sqlite",
]

from __future__ import annotations

"""SQLite connection pragmas (canonical).

Goal:
- reduce 'database is locked' incidents
- keep behavior deterministic
- avoid heavy tuning knobs

This module is safe to import from platform_layer/* (allowed by architecture tests).
"""

import sqlite3
from typing import Optional

from observability.platform.observability.silent import swallow
from runtime.platform.config.env_flags import env_int, env_str


def configure_sqlite(conn: sqlite3.Connection, *, prod: bool) -> None:
    """Apply canonical pragmas.

    NOTE:
    - WAL enables concurrent readers + one writer.
    - busy_timeout prevents immediate 'database is locked' under bursts.
    - synchronous=NORMAL is the standard WAL setting for durability vs throughput.
    """
    # Keep journal_mode=WAL explicit even if caller already set it.
    try:
        conn.execute("PRAGMA journal_mode=WAL;")
    except Exception:
        swallow(__name__, 'runtime/platform/outbox/sqlite_pragmas.py')

    # Busy timeout (milliseconds). Higher in prod.
    busy_ms = env_int("SQLITE_BUSY_TIMEOUT_MS", 5000 if prod else 1000)
    busy_ms = max(0, min(60_000, int(busy_ms)))
    try:
        conn.execute(f"PRAGMA busy_timeout={busy_ms};")
    except Exception:
        swallow(__name__, 'runtime/platform/outbox/sqlite_pragmas.py')

    # WAL + NORMAL sync: typical production choice on single-node SQLite.
    try:
        conn.execute("PRAGMA synchronous=NORMAL;")
    except Exception:
        swallow(__name__, 'runtime/platform/outbox/sqlite_pragmas.py')

    # Avoid temp file churn for sorts.
    try:
        conn.execute("PRAGMA temp_store=MEMORY;")
    except Exception:
        swallow(__name__, 'runtime/platform/outbox/sqlite_pragmas.py')

    # Safety invariant.
    try:
        conn.execute("PRAGMA foreign_keys=ON;")
    except Exception:
        swallow(__name__, 'runtime/platform/outbox/sqlite_pragmas.py')

    # Optional: limit WAL growth (checkpoint is best-effort).
    # This is intentionally conservative to avoid surprises.
    if prod:
        try:
            conn.execute("PRAGMA wal_autocheckpoint=1000;")  # pages
        except Exception:
            swallow(__name__, 'runtime/platform/outbox/sqlite_pragmas.py')


def is_prod_env() -> bool:
    env = env_str("ENV", "dev").strip().lower()
    return env in {"prod", "production"}

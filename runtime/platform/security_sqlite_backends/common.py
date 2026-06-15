from __future__ import annotations

import hashlib
import hmac
import json
import sqlite3
import time
from pathlib import Path
from typing import Any
from collections.abc import Mapping

CANON_PLATFORM_SECURITY_SQLITE_STORES = True

def _ensure_parent(db_path: str) -> None:
    Path(str(db_path)).parent.mkdir(parents=True, exist_ok=True)

def _connect(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    return conn

__all__ = [name for name in globals() if name.startswith("SQLite") or name.endswith("Backend") or name == "CANON_PLATFORM_SECURITY_SQLITE_STORES"]

__all__ = ["CANON_PLATFORM_SECURITY_SQLITE_STORES", "_ensure_parent", "_connect"]

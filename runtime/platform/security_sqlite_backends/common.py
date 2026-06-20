from __future__ import annotations

from pathlib import Path
from typing import Any

CANON_PLATFORM_SECURITY_SQLITE_STORES = True

def _ensure_parent(db_path: str) -> None:
    Path(str(db_path)).parent.mkdir(parents=True, exist_ok=True)

def _connect(db_path: str) -> Any:
    from runtime.platform.security_sqlite_stores import open_security_sqlite_connection

    return open_security_sqlite_connection(str(db_path))

__all__ = ["CANON_PLATFORM_SECURITY_SQLITE_STORES", "_ensure_parent", "_connect"]

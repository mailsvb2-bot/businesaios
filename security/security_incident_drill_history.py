from __future__ import annotations

from typing import Any, Mapping

from runtime.platform.security_sqlite_stores import SQLiteSecurityIncidentDrillHistoryBackend

CANON_SECURITY_INCIDENT_DRILL_HISTORY = True


class SQLiteSecurityIncidentDrillHistory:
    """Security-facing incident drill history facade.

    SQLite ownership lives in runtime.platform.security_sqlite_stores.
    """

    def __init__(self, db_path: str) -> None:
        self._backend = SQLiteSecurityIncidentDrillHistoryBackend(db_path)

    def append(self, *, drill_kind: str, ok: bool, payload: Mapping[str, Any] | None = None) -> None:
        self._backend.append(drill_kind=drill_kind, ok=ok, payload=payload)

    def latest(self, *, limit: int = 20) -> list[dict[str, Any]]:
        return self._backend.latest(limit=limit)


__all__ = ['CANON_SECURITY_INCIDENT_DRILL_HISTORY', 'SQLiteSecurityIncidentDrillHistory']

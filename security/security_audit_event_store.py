from __future__ import annotations

from typing import Any, Mapping

from runtime.platform.security_sqlite_stores import SQLiteSimpleAuditEventStoreBackend

CANON_SECURITY_AUDIT_EVENT_STORE = True


class SQLiteSecurityAuditEventStore:
    """Security-facing audit event store facade.

    SQLite ownership lives in runtime.platform.security_sqlite_stores.
    """

    def __init__(self, db_path: str) -> None:
        self._backend = SQLiteSimpleAuditEventStoreBackend(db_path)

    def append(self, *, event_kind: str, payload: Mapping[str, Any]) -> int:
        return self._backend.append(event_kind=event_kind, payload=payload)

    def latest(self, *, limit: int = 50) -> list[dict[str, Any]]:
        return self._backend.latest(limit=limit)


__all__ = ["CANON_SECURITY_AUDIT_EVENT_STORE", "SQLiteSecurityAuditEventStore"]

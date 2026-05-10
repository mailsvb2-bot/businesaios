from __future__ import annotations

from typing import Any, Mapping

from runtime.platform.security_sqlite_stores import SQLiteSecurityIncidentRegistryBackend

CANON_SECURITY_INCIDENT_REGISTRY = True


class SQLiteSecurityIncidentRegistry:
    """Security-facing incident registry facade.

    SQLite ownership lives in runtime.platform.security_sqlite_stores.
    """

    def __init__(self, db_path: str) -> None:
        self._backend = SQLiteSecurityIncidentRegistryBackend(db_path)

    def open_incident(self, *, incident_kind: str, payload: Mapping[str, Any]) -> int:
        return self._backend.open_incident(incident_kind=incident_kind, payload=payload)

    def resolve(self, *, incident_id: int, resolution_payload: Mapping[str, Any] | None = None) -> bool:
        return self._backend.resolve(incident_id=incident_id, resolution_payload=resolution_payload)

    def latest(self, *, limit: int = 50) -> list[dict[str, Any]]:
        return self._backend.latest(limit=limit)


__all__ = ['CANON_SECURITY_INCIDENT_REGISTRY', 'SQLiteSecurityIncidentRegistry']

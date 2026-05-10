from __future__ import annotations

from typing import Any, Mapping

from runtime.platform.security_sqlite_stores import SQLiteSecurityQuarantineRegistryBackend

CANON_SECURITY_QUARANTINE_REGISTRY = True


class SQLiteSecurityQuarantineRegistry:
    """Security-facing quarantine registry facade.

    SQLite ownership lives in runtime.platform.security_sqlite_stores.
    """

    def __init__(self, db_path: str) -> None:
        self._backend = SQLiteSecurityQuarantineRegistryBackend(db_path)

    def quarantine(self, *, entity_kind: str, entity_id: str, reason: str, payload: Mapping[str, Any] | None = None) -> None:
        self._backend.quarantine(entity_kind=entity_kind, entity_id=entity_id, reason=reason, payload=payload)

    def release(self, *, entity_kind: str, entity_id: str) -> bool:
        return self._backend.release(entity_kind=entity_kind, entity_id=entity_id)

    def is_quarantined(self, *, entity_kind: str, entity_id: str) -> bool:
        return self._backend.is_quarantined(entity_kind=entity_kind, entity_id=entity_id)

    def count_active(self, *, entity_kind: str | None = None) -> int:
        return self._backend.count_active(entity_kind=entity_kind)


__all__ = ["CANON_SECURITY_QUARANTINE_REGISTRY", "SQLiteSecurityQuarantineRegistry"]

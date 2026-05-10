from __future__ import annotations

from typing import Any, Mapping

from runtime.platform.security_sqlite_stores import SQLiteKeyRotationJournalBackend

CANON_KEY_ROTATION_JOURNAL = True


class SQLiteKeyRotationJournal:
    """Security-facing key rotation journal facade.

    SQLite ownership lives in runtime.platform.security_sqlite_stores.
    """

    def __init__(self, db_path: str) -> None:
        self._backend = SQLiteKeyRotationJournalBackend(db_path)

    def append(self, *, key_id: str, old_status: str, new_status: str, payload: Mapping[str, Any]) -> None:
        self._backend.append(key_id=key_id, old_status=old_status, new_status=new_status, payload=payload)

    def latest(self, *, limit: int = 50) -> list[dict[str, Any]]:
        return self._backend.latest(limit=limit)


__all__ = ['CANON_KEY_ROTATION_JOURNAL', 'SQLiteKeyRotationJournal']

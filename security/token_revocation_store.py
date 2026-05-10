from __future__ import annotations

from runtime.platform.security_sqlite_stores import SQLiteTokenRevocationStoreBackend

CANON_TOKEN_REVOCATION_STORE = True


class SQLiteTokenRevocationStore:
    """Security-facing token revocation facade.

    SQLite ownership lives in runtime.platform.security_sqlite_stores.
    """

    def __init__(self, db_path: str) -> None:
        self._backend = SQLiteTokenRevocationStoreBackend(db_path)

    def revoke(self, *, token_fingerprint: str, reason: str) -> None:
        self._backend.revoke(token_fingerprint=token_fingerprint, reason=reason)

    def is_revoked(self, *, token_fingerprint: str) -> bool:
        return self._backend.is_revoked(token_fingerprint=token_fingerprint)


__all__ = ["CANON_TOKEN_REVOCATION_STORE", "SQLiteTokenRevocationStore"]

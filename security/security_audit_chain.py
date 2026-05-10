from __future__ import annotations

from typing import Any, Mapping

from runtime.platform.security_sqlite_stores import SQLiteSecurityAuditChainBackend

CANON_SECURITY_AUDIT_CHAIN = True


class SQLiteSecurityAuditChain:
    """Security-facing tamper-evident audit chain facade.

    SQLite ownership lives in runtime.platform.security_sqlite_stores.
    """

    def __init__(self, db_path: str) -> None:
        self._backend = SQLiteSecurityAuditChainBackend(db_path)

    def append(self, *, event_kind: str, payload: Mapping[str, Any]) -> dict[str, Any]:
        return self._backend.append(event_kind=event_kind, payload=payload)

    def verify_chain(self) -> dict[str, Any]:
        return self._backend.verify_chain()


__all__ = ["CANON_SECURITY_AUDIT_CHAIN", "SQLiteSecurityAuditChain"]

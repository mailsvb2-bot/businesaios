from __future__ import annotations

from runtime.platform.security_sqlite_stores import SQLiteApprovalReplayGuardBackend

CANON_SECURITY_APPROVAL_REPLAY_GUARD = True


class SQLiteApprovalReplayGuard:
    """Security-facing single-use approval replay guard facade.

    SQLite ownership lives in runtime.platform.security_sqlite_stores.
    """

    def __init__(self, db_path: str) -> None:
        self._backend = SQLiteApprovalReplayGuardBackend(db_path)

    def consume(self, *, approval_id: str, operation_kind: str, actor: str) -> bool:
        return self._backend.consume(approval_id=approval_id, operation_kind=operation_kind, actor=actor)

    def has_been_consumed(self, *, approval_id: str) -> bool:
        return self._backend.has_been_consumed(approval_id=approval_id)


__all__ = ["CANON_SECURITY_APPROVAL_REPLAY_GUARD", "SQLiteApprovalReplayGuard"]

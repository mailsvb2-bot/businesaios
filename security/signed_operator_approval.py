from __future__ import annotations

from typing import Any, Mapping

from runtime.platform.security_sqlite_stores import SignedOperatorApprovalStoreBackend

CANON_SIGNED_OPERATOR_APPROVAL = True


class SignedOperatorApprovalStore:
    """Security-facing signed approval store facade.

    SQLite ownership lives in runtime.platform.security_sqlite_stores.
    """

    def __init__(self, db_path: str, shared_secret: str) -> None:
        self._backend = SignedOperatorApprovalStoreBackend(db_path, shared_secret)

    def grant(self, *, approval_id: str, operation_kind: str, actor: str, payload: Mapping[str, Any]) -> None:
        self._backend.grant(approval_id=approval_id, operation_kind=operation_kind, actor=actor, payload=payload)

    def verify(self, *, approval_id: str) -> dict[str, Any]:
        return self._backend.verify(approval_id=approval_id)


__all__ = ['CANON_SIGNED_OPERATOR_APPROVAL', 'SignedOperatorApprovalStore']

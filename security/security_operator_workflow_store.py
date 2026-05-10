from __future__ import annotations

from typing import Any, Mapping

from runtime.platform.security_sqlite_stores import SQLiteSecurityOperatorWorkflowStoreBackend

CANON_SECURITY_OPERATOR_WORKFLOW_STORE = True


class SQLiteSecurityOperatorWorkflowStore:
    """Security-facing operator workflow store facade.

    SQLite ownership lives in runtime.platform.security_sqlite_stores.
    """

    def __init__(self, db_path: str) -> None:
        self._backend = SQLiteSecurityOperatorWorkflowStoreBackend(db_path)

    def append_step(self, *, workflow_id: str, operation_kind: str, actor: str, step_kind: str, payload: Mapping[str, Any] | None = None) -> None:
        self._backend.append_step(workflow_id=workflow_id, operation_kind=operation_kind, actor=actor, step_kind=step_kind, payload=payload)

    def list_steps(self, *, workflow_id: str) -> list[dict[str, Any]]:
        return self._backend.list_steps(workflow_id=workflow_id)


__all__ = ['CANON_SECURITY_OPERATOR_WORKFLOW_STORE', 'SQLiteSecurityOperatorWorkflowStore']

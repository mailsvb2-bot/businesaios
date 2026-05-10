from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from runtime.platform.security_sqlite_stores import SQLiteSecurityDrillScheduleStoreBackend

CANON_SECURITY_DRILL_SCHEDULE_STORE = True


@dataclass(frozen=True)
class SecurityDrillSchedule:
    drill_id: str
    drill_kind: str
    actor: str
    target_entity_id: str
    interval_seconds: int
    next_run_epoch_s: int
    enabled: bool = True
    failure_escalation_kind: str = 'security-drill-failure'
    payload: Mapping[str, Any] | None = None


class SQLiteSecurityDrillScheduleStore:
    """Security-facing drill schedule facade.

    SQLite ownership lives in runtime.platform.security_sqlite_stores.
    """

    def __init__(self, db_path: str) -> None:
        self._backend = SQLiteSecurityDrillScheduleStoreBackend(db_path, SecurityDrillSchedule)

    def put(self, schedule: SecurityDrillSchedule) -> None:
        self._backend.put(schedule)

    def due(self, *, now_epoch_s: int | None = None, limit: int = 50) -> list[SecurityDrillSchedule]:
        return self._backend.due(now_epoch_s=now_epoch_s, limit=limit)

    def list_enabled(self) -> list[SecurityDrillSchedule]:
        return self._backend.list_enabled()

    def list_enabled_for_tenant(self, *, tenant_id: str) -> list[SecurityDrillSchedule]:
        tenant_norm = str(tenant_id or '').strip()
        if not tenant_norm:
            raise ValueError('tenant_id is required')
        return [item for item in self.list_enabled() if str((item.payload or {}).get('tenant_id', '')).strip() == tenant_norm]

    def get_for_tenant(self, *, tenant_id: str, drill_id: str) -> SecurityDrillSchedule:
        tenant_norm = str(tenant_id or '').strip()
        if not tenant_norm:
            raise ValueError('tenant_id is required')
        schedule = self._backend.get_by_drill_id(drill_id=drill_id)
        if str((schedule.payload or {}).get('tenant_id', '')).strip() != tenant_norm:
            raise PermissionError('cross-tenant drill schedule access denied')
        return schedule

    def mark_run(self, *, drill_id: str, next_run_epoch_s: int) -> None:
        self._backend.mark_run(drill_id=drill_id, next_run_epoch_s=next_run_epoch_s)


__all__ = ['CANON_SECURITY_DRILL_SCHEDULE_STORE', 'SecurityDrillSchedule', 'SQLiteSecurityDrillScheduleStore']

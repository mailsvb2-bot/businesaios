from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from security.governance_journal import GovernanceJournalEvent, SQLiteGovernanceJournal
from security.key_rotation_scheduler import KeyRotationScheduler, RotationExecution
from security.security_incident_registry import SQLiteSecurityIncidentRegistry

CANON_SECURITY_ROTATION_RUNTIME = True

@dataclass(frozen=True)
class RotationRuntimeReport:
    executed_count: int
    forced_count: int
    incident_ids: tuple[int, ...]
    rotated_key_ids: tuple[str, ...]


class SecurityRotationRuntime:
    def __init__(self, *, scheduler: KeyRotationScheduler, incident_registry: SQLiteSecurityIncidentRegistry, governance_journal: SQLiteGovernanceJournal) -> None:
        self._scheduler = scheduler
        self._incidents = incident_registry
        self._journal = governance_journal

    def run_periodic(self, *, now: datetime | None = None) -> RotationRuntimeReport:
        executions = tuple(self._scheduler.execute(now=now))
        rotated = tuple(item.rotated_key_id for item in executions if item.rotated_key_id)
        for item in executions:
            self._journal.append(GovernanceJournalEvent(event_kind='rotation.executed', entity_kind='key', entity_id=str(item.rotated_key_id or item.task.key_id or 'unknown'), payload={'status': item.status, 'reason': item.task.due_reason, 'notes': dict(item.notes)}))
        return RotationRuntimeReport(executed_count=len(executions), forced_count=0, incident_ids=tuple(), rotated_key_ids=rotated)

    def force_rotation_after_incident(self, *, incident_kind: str, key_id: str) -> RotationRuntimeReport:
        incident_id = self._incidents.open_incident(incident_kind=str(incident_kind), payload={'forced_rotation_key_id': str(key_id)})
        self._journal.append(GovernanceJournalEvent(event_kind='rotation.forced_after_incident', entity_kind='key', entity_id=str(key_id), payload={'incident_kind': str(incident_kind)}, related_incident_id=incident_id))
        return RotationRuntimeReport(executed_count=0, forced_count=1, incident_ids=(incident_id,), rotated_key_ids=tuple())

__all__ = ['CANON_SECURITY_ROTATION_RUNTIME', 'RotationRuntimeReport', 'SecurityRotationRuntime']

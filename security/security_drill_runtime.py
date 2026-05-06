from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

from security.governance_journal import GovernanceJournalEvent, SQLiteGovernanceJournal
from security.security_drill_executor import SecurityDrillExecutor
from security.security_drill_schedule_store import SQLiteSecurityDrillScheduleStore, SecurityDrillSchedule
from security.security_incident_registry import SQLiteSecurityIncidentRegistry

CANON_SECURITY_DRILL_RUNTIME = True

@dataclass(frozen=True)
class SecurityDrillRunOutcome:
    drill_id: str
    drill_kind: str
    success: bool
    escalated: bool
    reason: str
    details: dict[str, Any]

class SecurityDrillRuntime:
    def __init__(self, *, schedule_store: SQLiteSecurityDrillScheduleStore, drill_executor: SecurityDrillExecutor, incident_registry: SQLiteSecurityIncidentRegistry, governance_journal: SQLiteGovernanceJournal) -> None:
        self._schedule_store = schedule_store
        self._executor = drill_executor
        self._incidents = incident_registry
        self._journal = governance_journal

    def schedule(self, schedule: SecurityDrillSchedule) -> None:
        self._schedule_store.put(schedule)
        self._journal.append(GovernanceJournalEvent(event_kind='drill.scheduled', entity_kind='drill', entity_id=schedule.drill_id, payload={'drill_kind': schedule.drill_kind, 'target_entity_id': schedule.target_entity_id}, related_drill_kind=schedule.drill_kind))

    def run_due(self, *, now_epoch_s: int | None = None, limit: int = 25) -> list[SecurityDrillRunOutcome]:
        now = int(time.time()) if now_epoch_s is None else int(now_epoch_s)
        outcomes: list[SecurityDrillRunOutcome] = []
        for schedule in self._schedule_store.due(now_epoch_s=now, limit=limit):
            report = self._run_one(schedule)
            escalated = False
            if not report.success:
                incident_id = self._incidents.open_incident(incident_kind=schedule.failure_escalation_kind, payload={'drill_id': schedule.drill_id, 'drill_kind': schedule.drill_kind, 'target_entity_id': schedule.target_entity_id, 'reason': report.reason, 'details': report.details})
                escalated = True
                self._journal.append(GovernanceJournalEvent(event_kind='drill.failure_escalated', entity_kind='drill', entity_id=schedule.drill_id, payload={'reason': report.reason, 'details': report.details}, related_incident_id=incident_id, related_drill_kind=schedule.drill_kind))
            self._schedule_store.mark_run(drill_id=schedule.drill_id, next_run_epoch_s=now + int(schedule.interval_seconds))
            self._journal.append(GovernanceJournalEvent(event_kind='drill.executed', entity_kind='drill', entity_id=schedule.drill_id, payload={'success': report.success, 'reason': report.reason, 'details': report.details}, related_drill_kind=schedule.drill_kind))
            outcomes.append(SecurityDrillRunOutcome(drill_id=schedule.drill_id, drill_kind=schedule.drill_kind, success=bool(report.success), escalated=bool(escalated), reason=str(report.reason), details=dict(report.details)))
        return outcomes

    def _run_one(self, schedule: SecurityDrillSchedule):
        if schedule.drill_kind == 'token_quarantine_recovery':
            return self._executor.run_token_quarantine_recovery_drill(actor=schedule.actor, token_fingerprint=schedule.target_entity_id, reason='scheduled_drill')
        if schedule.drill_kind == 'secret_quarantine_recovery':
            return self._executor.run_secret_quarantine_recovery_drill(actor=schedule.actor, secret_id=schedule.target_entity_id, reason='scheduled_drill')
        raise ValueError(f'unsupported drill kind: {schedule.drill_kind}')

__all__ = ['CANON_SECURITY_DRILL_RUNTIME', 'SecurityDrillRunOutcome', 'SecurityDrillRuntime']

from __future__ import annotations

from dataclasses import dataclass

from security.governance_journal import SQLiteGovernanceJournal
from security.reencryption_job_store import SQLiteReencryptionJobStore
from security.security_incident_drill_history import SQLiteSecurityIncidentDrillHistory
from security.security_incident_registry import SQLiteSecurityIncidentRegistry
from security.security_quarantine_registry import SQLiteSecurityQuarantineRegistry

CANON_SECURITY_RUNTIME_SUMMARY = True

@dataclass(frozen=True)
class SecurityRuntimeSummary:
    open_incidents: int
    active_quarantines: int
    active_reencryption_jobs: int
    paused_reencryption_jobs: int
    latest_drill_ok: bool | None
    revoked_or_quarantined_entities: int
    rotation_backlog: int
    reencryption_backlog: int
    export_verification_failures: int
    latest_governance_events: tuple[dict[str, object], ...]
    latest_anomaly_flags: tuple[str, ...] = tuple()

class SecurityRuntimeSummaryService:
    def __init__(self, *, incident_registry: SQLiteSecurityIncidentRegistry, quarantine_registry: SQLiteSecurityQuarantineRegistry, reencryption_job_store: SQLiteReencryptionJobStore, drill_history: SQLiteSecurityIncidentDrillHistory, governance_journal: SQLiteGovernanceJournal | None = None) -> None:
        self._incidents = incident_registry
        self._quarantine = quarantine_registry
        self._jobs = reencryption_job_store
        self._drills = drill_history
        self._journal = governance_journal

    def build(self) -> SecurityRuntimeSummary:
        incidents = self._incidents.latest(limit=500)
        open_incidents = sum(1 for item in incidents if str(item.get('status')) == 'open')
        active_quarantines = self._quarantine.count_active()
        jobs = self._jobs.list_active()
        paused = sum(1 for item in jobs if item.status == 'paused')
        latest_drill = self._drills.latest(limit=1)
        latest_drill_ok = None if not latest_drill else bool(latest_drill[0].get('ok'))
        export_verification_failures = sum(1 for item in incidents if str(item.get('incident_kind')) == 'security-export-verification-failure' and str(item.get('status')) == 'open')
        latest_events = tuple(self._journal.latest(limit=5) if self._journal is not None else [])
        anomaly_flags = tuple(sorted({str(item.get('incident_kind')) for item in incidents if 'approval-replay' in str(item.get('incident_kind')) or 'chaos:' in str(item.get('incident_kind'))}))
        return SecurityRuntimeSummary(open_incidents=open_incidents, active_quarantines=active_quarantines, active_reencryption_jobs=len(jobs), paused_reencryption_jobs=paused, latest_drill_ok=latest_drill_ok, revoked_or_quarantined_entities=active_quarantines + open_incidents, rotation_backlog=len(jobs), reencryption_backlog=sum(1 for item in jobs if item.status in {'queued', 'running', 'paused'}), export_verification_failures=export_verification_failures, latest_governance_events=latest_events, latest_anomaly_flags=anomaly_flags)

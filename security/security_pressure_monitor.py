from __future__ import annotations

from dataclasses import dataclass

from security.anomaly_detector import AnomalyDetector, AnomalyVerdict
from security.behavioral_baseline import BehavioralBaseline
from security.reencryption_job_store import SQLiteReencryptionJobStore
from security.security_incident_registry import SQLiteSecurityIncidentRegistry
from security.security_quarantine_registry import SQLiteSecurityQuarantineRegistry

CANON_SECURITY_PRESSURE_MONITOR = True

@dataclass(frozen=True)
class SecurityPressureSnapshot:
    revoke_spike: AnomalyVerdict
    quarantine_surge: AnomalyVerdict
    reencryption_backlog_growth: AnomalyVerdict
    approval_replay_anomaly: AnomalyVerdict


class SecurityPressureMonitor:
    def __init__(self, *, incident_registry: SQLiteSecurityIncidentRegistry, quarantine_registry: SQLiteSecurityQuarantineRegistry, reencryption_job_store: SQLiteReencryptionJobStore, baseline: BehavioralBaseline | None = None) -> None:
        self._incidents = incident_registry
        self._quarantine = quarantine_registry
        self._jobs = reencryption_job_store
        self._baseline = baseline or BehavioralBaseline()
        self._detector = AnomalyDetector(self._baseline)

    def observe_baseline(self, *, revoke_count: float, quarantine_count: float, reencryption_backlog: float, approval_replay_count: float) -> None:
        self._baseline.observe(key='security.revoke_count', value=revoke_count)
        self._baseline.observe(key='security.quarantine_count', value=quarantine_count)
        self._baseline.observe(key='security.reencryption_backlog', value=reencryption_backlog)
        self._baseline.observe(key='security.approval_replay_count', value=approval_replay_count)

    def snapshot(self) -> SecurityPressureSnapshot:
        incidents = self._incidents.latest(limit=500)
        revoke_count = sum(1 for item in incidents if 'revoke' in str(item.get('incident_kind', '')) and str(item.get('status')) == 'open')
        approval_replay_count = sum(1 for item in incidents if 'approval-replay' in str(item.get('incident_kind', '')) and str(item.get('status')) == 'open')
        quarantine_count = self._quarantine.count_active()
        reencryption_backlog = sum(1 for item in self._jobs.list_active() if item.status in {'pending', 'running', 'paused'})
        approval_verdict = self._detector.score(key='security.approval_replay_count', observed_value=float(approval_replay_count))
        if not approval_verdict.anomalous and approval_replay_count > 0:
            approval_verdict = AnomalyVerdict(anomalous=True, score=max(float(approval_verdict.score), 1.0), reason='approval_replay_detected', observed_value=float(approval_replay_count), mean=approval_verdict.mean, stddev=approval_verdict.stddev, z_score=approval_verdict.z_score, labels=dict(approval_verdict.labels))
        return SecurityPressureSnapshot(
            revoke_spike=self._detector.score(key='security.revoke_count', observed_value=float(revoke_count)),
            quarantine_surge=self._detector.score(key='security.quarantine_count', observed_value=float(quarantine_count)),
            reencryption_backlog_growth=self._detector.score(key='security.reencryption_backlog', observed_value=float(reencryption_backlog)),
            approval_replay_anomaly=approval_verdict,
        )

__all__ = ['CANON_SECURITY_PRESSURE_MONITOR', 'SecurityPressureMonitor', 'SecurityPressureSnapshot']

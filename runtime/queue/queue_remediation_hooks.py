"""Operator-facing remediation hooks for queue health.

This module stays strictly operational:
- derive safe remediation options from queue health facts
- optionally execute explicit operator-selected maintenance hooks
- never create a second decision center

No business planning or autonomous intent is introduced here.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Protocol

from runtime.queue.job_contract import normalize_now
from runtime.queue.job_janitor import JobQueueJanitor, QueueJanitorReport
from runtime.queue.queue_alerts import QueueAlert
from runtime.queue.queue_health_monitor import QueueHealthMonitor, QueueHealthMonitorReport
from runtime.queue.queue_metrics_retention import QueueMetricsRetentionManager, QueueMetricsRetentionReport
from runtime.queue.queue_slo import QueueSLOReport

CANON_RUNTIME_QUEUE_REMEDIATION_HOOKS = True


class QueueRemediationAuditSink(Protocol):
    def record_plan(self, plan: QueueRemediationPlan) -> object: ...
    def record_execution(self, report: QueueRemediationExecutionReport) -> object: ...


@dataclass(frozen=True)
class QueueRemediationHook:
    tenant_id: str
    queue_name: str
    code: str
    label: str
    description: str
    severity: str
    operator_required: bool = True
    category: str = 'inspection'
    runbook_hint: str | None = None
    metadata: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class QueueRemediationPlan:
    tenant_id: str
    queue_name: str
    hooks: tuple[QueueRemediationHook, ...]
    generated_at: datetime


@dataclass(frozen=True)
class QueueRemediationExecutionReport:
    tenant_id: str
    queue_name: str
    hook_code: str
    executed: bool
    reason: str
    executed_at: datetime
    category: str = 'inspection'
    janitor_report: QueueJanitorReport | None = None
    retention_report: QueueMetricsRetentionReport | None = None
    health_report: QueueHealthMonitorReport | None = None
    metadata: dict[str, object] = field(default_factory=dict)


class QueueRemediationPlanner:
    def plan(
        self,
        *,
        report: QueueSLOReport,
        alerts: tuple[QueueAlert, ...] = (),
        now: datetime | None = None,
    ) -> QueueRemediationPlan:
        moment = normalize_now(now)
        hooks: list[QueueRemediationHook] = []
        reasons = set(report.reasons)
        severities = {str(getattr(a, 'code', '')).strip(): str(getattr(a, 'severity', 'warning')).strip() for a in alerts}
        alert_codes = {str(getattr(a, 'code', '')).strip() for a in alerts}

        if 'janitor_stale' in reasons:
            hooks.append(self._hook(report, 'run_janitor_tick', 'Run janitor tick', 'Reclaim expired claims and refresh janitor heartbeat.', severities.get('janitor_stale', 'critical'), category='recovery', runbook_hint='Recover expired claims before scaling workers.'))
        if 'leadership_stale' in reasons:
            hooks.append(self._hook(report, 'refresh_health_sample', 'Refresh leadership health', 'Re-sample queue health after leadership heartbeat or failover.', severities.get('leadership_stale', 'critical'), category='verification', runbook_hint='Verify leader lease is healthy before other interventions.'))
        if 'pending_jobs_exceeded' in reasons:
            hooks.append(self._hook(report, 'open_queue_history', 'Inspect queue backlog history', 'Review queue history and backlog spikes before changing worker capacity.', severities.get('pending_jobs_exceeded', 'error'), category='inspection', runbook_hint='Inspect backlog growth and queue timeline.'))
        if 'active_claims_exceeded' in reasons:
            hooks.append(self._hook(report, 'inspect_active_claims', 'Inspect active claims', 'Review long-running claims and confirm workers still hold live leases.', severities.get('active_claims_exceeded', 'error'), category='inspection', runbook_hint='Look for stalled workers or oversized lease windows.'))
        if 'dead_letter_jobs_exceeded' in reasons:
            hooks.append(self._hook(report, 'review_dead_letters', 'Review dead-letter jobs', 'Open dead-letter history and inspect repeated failures before replay.', severities.get('dead_letter_jobs_exceeded', 'critical'), category='inspection', runbook_hint='Check repeated job_type failures before replaying.'))
        if {'queue_soft_pressure', 'queue_hard_pressure', 'queue_claims_hard_pressure'} & alert_codes:
            hooks.append(self._hook(report, 'inspect_backpressure', 'Inspect queue backpressure', 'Review pressure alerts, claim headroom, and queue growth before scaling workers or changing limits.', _max_severity(severities, ('queue_soft_pressure', 'queue_hard_pressure', 'queue_claims_hard_pressure'), default='warning'), category='inspection', runbook_hint='Inspect backlog pressure before applying manual capacity changes.'))
        if {'tenant_starvation_risk', 'tenant_fairness_gap_high'} & alert_codes:
            hooks.append(self._hook(report, 'inspect_tenant_fairness', 'Inspect tenant fairness', 'Review tenant fairness gaps and starvation risk before changing per-tenant limits.', _max_severity(severities, ('tenant_starvation_risk', 'tenant_fairness_gap_high'), default='warning'), category='inspection', runbook_hint='Check whether one tenant is monopolizing shared queue budget.'))
        if report.status != 'healthy':
            hooks.append(self._hook(report, 'apply_metrics_retention', 'Compact queue history evidence', 'Compact and retain queue health evidence so operator history stays bounded and readable.', 'warning', category='maintenance', runbook_hint='Compact stale rollups after incident review.'))
        hooks.append(self._hook(report, 'refresh_health_sample', 'Refresh queue health', 'Take a fresh queue health sample after operational work.', 'warning', category='verification', runbook_hint='Refresh evidence after any remediation.'))

        deduped: list[QueueRemediationHook] = []
        seen: set[str] = set()
        for hook in hooks:
            if hook.code in seen:
                continue
            seen.add(hook.code)
            deduped.append(hook)
        return QueueRemediationPlan(
            tenant_id=report.tenant_id,
            queue_name=report.queue_name,
            hooks=tuple(deduped),
            generated_at=moment,
        )

    @staticmethod
    def _hook(
        report: QueueSLOReport,
        code: str,
        label: str,
        description: str,
        severity: str,
        *,
        category: str,
        runbook_hint: str | None = None,
    ) -> QueueRemediationHook:
        return QueueRemediationHook(
            tenant_id=report.tenant_id,
            queue_name=report.queue_name,
            code=code,
            label=label,
            description=description,
            severity=str(severity or 'warning').strip(),
            operator_required=True,
            category=str(category).strip() or 'inspection',
            runbook_hint=(str(runbook_hint).strip() or None) if runbook_hint is not None else None,
            metadata={'reasons': tuple(report.reasons)},
        )


class QueueRemediationCoordinator:
    def __init__(
        self,
        *,
        planner: QueueRemediationPlanner | None = None,
        janitor: JobQueueJanitor | None = None,
        metrics_retention: QueueMetricsRetentionManager | None = None,
        health_monitor: QueueHealthMonitor | None = None,
        audit_sink: QueueRemediationAuditSink | None = None,
    ) -> None:
        self._planner = planner or QueueRemediationPlanner()
        self._janitor = janitor
        self._metrics_retention = metrics_retention
        self._health_monitor = health_monitor
        self._audit_sink = audit_sink

    def plan(
        self,
        *,
        report: QueueSLOReport,
        alerts: tuple[QueueAlert, ...] = (),
        now: datetime | None = None,
    ) -> QueueRemediationPlan:
        plan = self._planner.plan(report=report, alerts=alerts, now=now)
        if self._audit_sink is not None:
            self._audit_sink.record_plan(plan)
        return plan

    def execute(
        self,
        *,
        tenant_id: str,
        queue_name: str,
        hook_code: str,
        now: datetime | None = None,
    ) -> QueueRemediationExecutionReport:
        moment = normalize_now(now)
        code = str(hook_code).strip()
        if code == 'run_janitor_tick':
            if self._janitor is None:
                report = self._not_executed(tenant_id, queue_name, code, 'janitor_not_configured', moment, category='recovery')
                self._record_execution(report)
                return report
            report = QueueRemediationExecutionReport(
                tenant_id=str(tenant_id).strip(),
                queue_name=str(queue_name).strip(),
                hook_code=code,
                executed=True,
                reason='janitor_tick_executed',
                executed_at=moment,
                category='recovery',
                janitor_report=self._janitor.tick(tenant_id=tenant_id, queue_name=queue_name, now=moment),
                metadata={'safe_action': True},
            )
            self._record_execution(report)
            return report
        if code == 'apply_metrics_retention':
            if self._metrics_retention is None:
                report = self._not_executed(tenant_id, queue_name, code, 'metrics_retention_not_configured', moment, category='maintenance')
                self._record_execution(report)
                return report
            report = QueueRemediationExecutionReport(
                tenant_id=str(tenant_id).strip(),
                queue_name=str(queue_name).strip(),
                hook_code=code,
                executed=True,
                reason='metrics_retention_applied',
                executed_at=moment,
                category='maintenance',
                retention_report=self._metrics_retention.apply(tenant_id=tenant_id, queue_name=queue_name, now=moment),
                metadata={'safe_action': True},
            )
            self._record_execution(report)
            return report
        if code == 'refresh_health_sample':
            if self._health_monitor is None:
                report = self._not_executed(tenant_id, queue_name, code, 'health_monitor_not_configured', moment, category='verification')
                self._record_execution(report)
                return report
            report = QueueRemediationExecutionReport(
                tenant_id=str(tenant_id).strip(),
                queue_name=str(queue_name).strip(),
                hook_code=code,
                executed=True,
                reason='health_sample_refreshed',
                executed_at=moment,
                category='verification',
                health_report=self._health_monitor.sample(tenant_id=tenant_id, queue_name=queue_name, now=moment),
                metadata={'safe_action': True},
            )
            self._record_execution(report)
            return report
        report = self._not_executed(tenant_id, queue_name, code, 'operator_review_required', moment, category='inspection')
        self._record_execution(report)
        return report

    def _record_execution(self, report: QueueRemediationExecutionReport) -> None:
        if self._audit_sink is not None:
            self._audit_sink.record_execution(report)

    @staticmethod
    def _not_executed(
        tenant_id: str,
        queue_name: str,
        hook_code: str,
        reason: str,
        moment: datetime,
        *,
        category: str,
    ) -> QueueRemediationExecutionReport:
        return QueueRemediationExecutionReport(
            tenant_id=str(tenant_id).strip(),
            queue_name=str(queue_name).strip(),
            hook_code=str(hook_code).strip(),
            executed=False,
            reason=str(reason).strip(),
            executed_at=moment,
            category=str(category).strip() or 'inspection',
            metadata={'safe_action': False},
        )


def _max_severity(values: dict[str, str], keys: tuple[str, ...], *, default: str) -> str:
    rank = {'warning': 1, 'error': 2, 'critical': 3}
    best = str(default).strip() or 'warning'
    for key in keys:
        candidate = str(values.get(key, '')).strip()
        if rank.get(candidate, 0) > rank.get(best, 0):
            best = candidate
    return best


__all__ = [
    'CANON_RUNTIME_QUEUE_REMEDIATION_HOOKS',
    'QueueRemediationAuditSink',
    'QueueRemediationCoordinator',
    'QueueRemediationExecutionReport',
    'QueueRemediationHook',
    'QueueRemediationPlan',
    'QueueRemediationPlanner',
]

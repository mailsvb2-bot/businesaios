from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from entrypoints.api.queue_ops_models import (
    QueueOpsAuditQuery,
    QueueOpsViewResponse,
    QueueRemediationAnalyticsResponse,
    QueueRemediationAuditResponse,
    QueueRemediationExecuteCommand,
    QueueRemediationExecutionResponse,
)
from entrypoints.api.queue_ops_route_support import (
    alert_dict,
    build_consistency_snapshot,
    build_data_freshness,
    build_evidence_timeline,
    build_operator_summary,
    build_timeline_rows,
    normalize_hook_code,
    normalize_limit,
    normalize_optional,
    normalize_queue_name,
    normalize_source,
    normalize_tenant_id,
    sanitize_hook_item,
    sanitize_metadata,
    slo_dict,
)
from runtime.queue.job_contract import normalize_now
from runtime.queue.job_store import InMemoryJobStore
from runtime.queue.queue_alerts import InMemoryQueueAlertSink, QueueAlert, QueueAlertRouter
from runtime.queue.queue_health_monitor import QueueHealthMonitor
from runtime.queue.queue_metrics_rollup_sqlite import SqliteQueueMetricsRollupStore
from runtime.queue.queue_observability import QueueObservabilityRegistry
from runtime.queue.queue_remediation_analytics import QueueRemediationAnalyticsService
from runtime.queue.queue_remediation_audit_sqlite import SqliteQueueRemediationAuditStore
from runtime.queue.queue_remediation_hooks import QueueRemediationCoordinator
from runtime.queue.queue_remediation_route_history_sqlite import SqliteQueueRemediationRouteHistoryStore
from runtime.queue.queue_slo import QueueSLOEvaluator

CANON_API_QUEUE_OPS_ROUTE_HANDLERS_FINAL_OWNER = True
CANON_API_QUEUE_OPS_ROUTE_HANDLERS = True


@dataclass(frozen=True)
class QueueOpsRouteHandlers:
    store: Any = field(default_factory=InMemoryJobStore)
    observability: QueueObservabilityRegistry = field(default_factory=QueueObservabilityRegistry)
    alert_sink: Any = field(default_factory=InMemoryQueueAlertSink)
    rollup_store: SqliteQueueMetricsRollupStore | None = None
    remediation_audit_store: SqliteQueueRemediationAuditStore | None = None
    remediation_route_history_store: SqliteQueueRemediationRouteHistoryStore | None = None
    health_monitor: QueueHealthMonitor = field(init=False)
    remediation: QueueRemediationCoordinator = field(init=False)
    remediation_analytics: QueueRemediationAnalyticsService = field(init=False)

    def __post_init__(self) -> None:
        evaluator = QueueSLOEvaluator(store=self.store, observability=self.observability)
        alert_router = QueueAlertRouter(evaluator=evaluator, observability=self.observability, sink=self.alert_sink)
        rollup_store = self.rollup_store if self.rollup_store is not None else SqliteQueueMetricsRollupStore()
        audit_store = self.remediation_audit_store if self.remediation_audit_store is not None else SqliteQueueRemediationAuditStore()
        route_history_store = (
            self.remediation_route_history_store
            if self.remediation_route_history_store is not None
            else SqliteQueueRemediationRouteHistoryStore()
        )
        monitor = QueueHealthMonitor(evaluator=evaluator, alert_router=alert_router, rollup_store=rollup_store)
        remediation = QueueRemediationCoordinator(health_monitor=monitor, audit_sink=audit_store)
        analytics = QueueRemediationAnalyticsService(audit_store=audit_store, route_history_store=route_history_store)
        object.__setattr__(self, 'health_monitor', monitor)
        object.__setattr__(self, 'remediation', remediation)
        object.__setattr__(self, 'remediation_analytics', analytics)
        object.__setattr__(self, 'rollup_store', rollup_store)
        object.__setattr__(self, 'remediation_audit_store', audit_store)
        object.__setattr__(self, 'remediation_route_history_store', route_history_store)

    def get_queue_ops_view(
        self,
        *,
        tenant_id: str,
        queue_name: str,
        actor_id: str | None = None,
        request_id: str | None = None,
        source: str = 'control_plane',
        now: datetime | None = None,
    ) -> dict[str, Any]:
        moment = normalize_now(now)
        normalized_tenant_id = normalize_tenant_id(tenant_id)
        normalized_queue_name = normalize_queue_name(queue_name)
        normalized_source = normalize_source(source)
        normalized_actor_id = normalize_optional(actor_id)
        normalized_request_id = normalize_optional(request_id)
        monitor_report = self.health_monitor.sample(tenant_id=normalized_tenant_id, queue_name=normalized_queue_name, now=moment)
        plan = self.remediation.plan(report=monitor_report.slo, alerts=monitor_report.alerts, now=moment)
        recent_alerts = self._recent_alerts(tenant_id=normalized_tenant_id, queue_name=normalized_queue_name, limit=20)
        rollup_summary = self.rollup_store.summarize(tenant_id=normalized_tenant_id, queue_name=normalized_queue_name) if self.rollup_store is not None else None
        analytics_preview = self.remediation_analytics.summarize(tenant_id=normalized_tenant_id, queue_name=normalized_queue_name, limit=50)
        audit_preview = self._build_audit_preview(tenant_id=normalized_tenant_id, queue_name=normalized_queue_name, limit=10)
        approval_preview = self._build_approval_preview(plan=plan)
        timeline_preview = self._build_timeline_preview(tenant_id=normalized_tenant_id, queue_name=normalized_queue_name, limit=12)
        trend_preview = self._build_trend_preview(tenant_id=normalized_tenant_id, queue_name=normalized_queue_name, now=moment)
        data_freshness = build_data_freshness(monitor_report=monitor_report, rollup_summary=rollup_summary, now=moment)
        evidence_timeline = build_evidence_timeline(monitor_report=monitor_report, recent_alerts=recent_alerts, remediation_plan=plan, approval_preview=approval_preview, route_timeline=timeline_preview, now=moment, limit=20)
        consistency = build_consistency_snapshot(monitor_report=monitor_report, recent_alerts=recent_alerts, approval_preview=approval_preview, audit_preview=audit_preview, analytics_preview=analytics_preview, trend_preview=trend_preview, data_freshness=data_freshness)
        operator_summary = build_operator_summary(monitor_report=monitor_report, analytics_preview=analytics_preview, audit_preview=audit_preview, approval_preview=approval_preview, trend_preview=trend_preview, data_freshness=data_freshness, consistency=consistency)
        self._record_route_event(
            tenant_id=normalized_tenant_id,
            queue_name=normalized_queue_name,
            action='get_queue_ops_view',
            actor_id=normalized_actor_id,
            request_id=normalized_request_id,
            source=normalized_source,
            status='ok',
            metadata={'hook_count': len(plan.hooks), 'status': monitor_report.slo.status, 'alert_count': len(monitor_report.alerts), 'backpressure_reason': None if monitor_report.backpressure is None else monitor_report.backpressure.global_verdict.reason, 'approval_required_count': int(approval_preview.get('approval_required_count', 0) or 0), 'freshness_state': data_freshness.get('state'), 'consistency_state': consistency.get('state'), 'request_id': normalized_request_id, 'actor_id': normalized_actor_id},
            now=moment,
        )
        return QueueOpsViewResponse(
            tenant_id=normalized_tenant_id,
            queue_name=normalized_queue_name,
            health=slo_dict(monitor_report.slo),
            alerts=tuple(alert_dict(item) for item in recent_alerts),
            rollup_summary=None if rollup_summary is None else {
                'samples': rollup_summary.samples,
                'latest_status': rollup_summary.latest_status,
                'max_pending_jobs': rollup_summary.max_pending_jobs,
                'max_active_claims': rollup_summary.max_active_claims,
                'max_dead_letter_jobs': rollup_summary.max_dead_letter_jobs,
                'last_observed_at': None if rollup_summary.last_observed_at is None else rollup_summary.last_observed_at.isoformat(),
            },
            remediation_plan={
                'generated_at': plan.generated_at.isoformat(),
                'hooks': tuple(
                    {
                        'code': hook.code,
                        'label': hook.label,
                        'description': hook.description,
                        'severity': hook.severity,
                        'operator_required': hook.operator_required,
                        'category': hook.category,
                        'runbook_hint': hook.runbook_hint,
                        'metadata': sanitize_metadata(getattr(hook, 'metadata', None)),
                    }
                    for hook in plan.hooks
                ),
            },
            analytics_preview={
                'plan_count': analytics_preview.plan_count,
                'execution_count': analytics_preview.execution_count,
                'route_event_count': analytics_preview.route_event_count,
                'most_used_hook_code': analytics_preview.most_used_hook_code,
                'top_unexecuted_hook_code': analytics_preview.top_unexecuted_hook_code,
                'execution_rate': analytics_preview.execution_rate,
                'source_counts': dict(analytics_preview.source_counts),
                'status_counts': dict(analytics_preview.status_counts),
                'hook_offer_counts': dict(analytics_preview.hook_offer_counts),
                'reason_counts': dict(analytics_preview.reason_counts),
            },
            audit_preview=audit_preview,
            operator_summary=operator_summary,
            timeline_preview=timeline_preview,
            approval_preview=approval_preview,
            trend_preview=trend_preview,
            data_freshness=data_freshness,
            evidence_timeline=evidence_timeline,
            consistency=consistency,
        ).as_dict()

    def get_remediation_analytics(
        self,
        *,
        tenant_id: str,
        queue_name: str,
        limit: int = 200,
        actor_id: str | None = None,
        request_id: str | None = None,
        source: str = 'control_plane',
        now: datetime | None = None,
    ) -> dict[str, Any]:
        normalized_tenant_id = normalize_tenant_id(tenant_id)
        normalized_queue_name = normalize_queue_name(queue_name)
        normalized_actor_id = normalize_optional(actor_id)
        normalized_request_id = normalize_optional(request_id)
        normalized_limit = normalize_limit(limit, default=200)
        analytics = self.remediation_analytics.summarize(tenant_id=normalized_tenant_id, queue_name=normalized_queue_name, limit=normalized_limit)
        self._record_route_event(
            tenant_id=normalized_tenant_id,
            queue_name=normalized_queue_name,
            action='get_remediation_analytics',
            actor_id=normalized_actor_id,
            request_id=normalized_request_id,
            source=normalize_source(source),
            status='ok',
            metadata={'execution_count': analytics.execution_count, 'route_event_count': analytics.route_event_count},
            now=now,
        )
        return QueueRemediationAnalyticsResponse(
            tenant_id=analytics.tenant_id,
            queue_name=analytics.queue_name,
            analytics=analytics.as_dict(),
        ).as_dict()

    def execute_remediation_hook(
        self,
        *,
        tenant_id: str,
        queue_name: str,
        hook_code: str,
        actor_id: str | None = None,
        request_id: str | None = None,
        source: str = 'control_plane',
        now: datetime | None = None,
    ) -> dict[str, Any]:
        moment = normalize_now(now)
        command = QueueRemediationExecuteCommand(
            tenant_id=normalize_tenant_id(tenant_id),
            queue_name=normalize_queue_name(queue_name),
            hook_code=normalize_hook_code(hook_code),
            actor_id=normalize_optional(actor_id),
            request_id=normalize_optional(request_id),
            source=normalize_source(source),
        )
        report = self.remediation.execute(tenant_id=command.tenant_id, queue_name=command.queue_name, hook_code=command.hook_code, now=moment)
        self._record_route_event(
            tenant_id=command.tenant_id,
            queue_name=command.queue_name,
            action='execute_remediation_hook',
            actor_id=command.actor_id,
            request_id=command.request_id,
            source=command.source,
            status='executed' if report.executed else 'review_required',
            metadata={'hook_code': report.hook_code, 'reason': report.reason, 'category': report.category},
            now=moment,
        )
        return QueueRemediationExecutionResponse(
            tenant_id=report.tenant_id,
            queue_name=report.queue_name,
            hook_code=report.hook_code,
            executed=report.executed,
            reason=report.reason,
            executed_at=report.executed_at.isoformat(),
            route_recorded=self.remediation_route_history_store is not None,
        ).as_dict()

    def list_remediation_audit(
        self,
        *,
        tenant_id: str,
        queue_name: str,
        limit: int = 50,
        action: str | None = None,
        status: str | None = None,
        source_filter: str | None = None,
        timeline_limit: int = 25,
        actor_id: str | None = None,
        request_id: str | None = None,
        source: str = 'control_plane',
        now: datetime | None = None,
    ) -> dict[str, Any]:
        query = QueueOpsAuditQuery(
            tenant_id=normalize_tenant_id(tenant_id),
            queue_name=normalize_queue_name(queue_name),
            limit=normalize_limit(limit, default=50),
            action=normalize_optional(action),
            status=normalize_optional(status),
            source=normalize_optional(source_filter),
            timeline_limit=normalize_limit(timeline_limit, default=25, upper=200),
        )
        normalized_actor_id = normalize_optional(actor_id)
        normalized_request_id = normalize_optional(request_id)
        plans = self.remediation_audit_store.list_plan_entries(tenant_id=query.tenant_id, queue_name=query.queue_name, limit=query.limit) if self.remediation_audit_store is not None else ()
        executions = self.remediation_audit_store.list_execution_entries(tenant_id=query.tenant_id, queue_name=query.queue_name, limit=query.limit) if self.remediation_audit_store is not None else ()
        route_history = self.remediation_route_history_store.list_entries(tenant_id=query.tenant_id, queue_name=query.queue_name, limit=query.limit, action=query.action, status=query.status, source=query.source) if self.remediation_route_history_store is not None else ()
        self._record_route_event(
            tenant_id=query.tenant_id,
            queue_name=query.queue_name,
            action='list_remediation_audit',
            actor_id=normalized_actor_id,
            request_id=normalized_request_id,
            source=normalize_source(source),
            status='ok',
            metadata={'plan_count': len(plans), 'execution_count': len(executions), 'timeline_limit': query.timeline_limit, 'action_filter': query.action, 'status_filter': query.status, 'source_filter': query.source},
            now=now,
        )
        return QueueRemediationAuditResponse(
            tenant_id=query.tenant_id,
            queue_name=query.queue_name,
            plans=tuple(
                {
                    'generated_at': entry.generated_at.isoformat(),
                    'hooks': tuple(sanitize_hook_item(item) for item in tuple(entry.hooks or ())),
                }
                for entry in plans
            ),
            executions=tuple(
                {
                    'hook_code': entry.hook_code,
                    'executed': entry.executed,
                    'reason': entry.reason,
                    'executed_at': entry.executed_at.isoformat(),
                    'category': entry.category,
                    'metadata': sanitize_metadata(getattr(entry, 'metadata', None)),
                }
                for entry in executions
            ),
            route_history=tuple(
                {
                    'action': entry.action,
                    'source': entry.source,
                    'actor_id': entry.actor_id,
                    'request_id': entry.request_id,
                    'status': entry.status,
                    'metadata': sanitize_metadata(getattr(entry, 'metadata', None)),
                    'recorded_at': entry.recorded_at.isoformat(),
                }
                for entry in route_history
            ),
            timeline=build_timeline_rows(plans=plans, executions=executions, route_history=route_history, limit=query.timeline_limit),
        ).as_dict()

    def _build_audit_preview(self, *, tenant_id: str, queue_name: str, limit: int = 10) -> dict[str, Any]:
        normalized_limit = normalize_limit(limit, default=10)
        plans = self.remediation_audit_store.list_plan_entries(tenant_id=tenant_id, queue_name=queue_name, limit=normalized_limit) if self.remediation_audit_store is not None else ()
        executions = self.remediation_audit_store.list_execution_entries(tenant_id=tenant_id, queue_name=queue_name, limit=normalized_limit) if self.remediation_audit_store is not None else ()
        route_history = self.remediation_route_history_store.list_entries(tenant_id=tenant_id, queue_name=queue_name, limit=normalized_limit) if self.remediation_route_history_store is not None else ()
        latest_execution = executions[0] if executions else None
        latest_route = route_history[0] if route_history else None
        latest_plan = plans[0] if plans else None
        return {
            'plan_count': len(plans),
            'execution_count': len(executions),
            'route_event_count': len(route_history),
            'plan_preview_count': len(plans),
            'execution_preview_count': len(executions),
            'route_event_preview_count': len(route_history),
            'timeline_event_count': len(plans) + len(executions) + len(route_history),
            'preview_limited': True,
            'latest_plan_generated_at': None if latest_plan is None else latest_plan.generated_at.isoformat(),
            'latest_execution_hook_code': None if latest_execution is None else latest_execution.hook_code,
            'latest_execution_reason': None if latest_execution is None else latest_execution.reason,
            'latest_route_action': None if latest_route is None else latest_route.action,
            'latest_route_status': None if latest_route is None else latest_route.status,
        }

    def _build_approval_preview(self, *, plan: Any) -> dict[str, Any]:
        hooks = tuple(getattr(plan, 'hooks', ()) or ())
        approval_required = tuple(hook for hook in hooks if bool(getattr(hook, 'operator_required', True)))
        return {
            'approval_required_count': len(approval_required),
            'approval_required_hook_codes': tuple(str(getattr(hook, 'code', '') or '').strip() for hook in approval_required if str(getattr(hook, 'code', '') or '').strip()),
            'approval_required_hooks': tuple(str(getattr(hook, 'code', '') or '').strip() for hook in approval_required if str(getattr(hook, 'code', '') or '').strip()),
            'review_categories': tuple(sorted({str(getattr(hook, 'category', '') or '').strip() for hook in approval_required if str(getattr(hook, 'category', '') or '').strip()})),
        }

    def _build_timeline_preview(self, *, tenant_id: str, queue_name: str, limit: int = 12) -> tuple[dict[str, Any], ...]:
        normalized_limit = normalize_limit(limit, default=12, upper=200)
        plans = self.remediation_audit_store.list_plan_entries(tenant_id=tenant_id, queue_name=queue_name, limit=normalized_limit) if self.remediation_audit_store is not None else ()
        executions = self.remediation_audit_store.list_execution_entries(tenant_id=tenant_id, queue_name=queue_name, limit=normalized_limit) if self.remediation_audit_store is not None else ()
        route_history = self.remediation_route_history_store.list_entries(tenant_id=tenant_id, queue_name=queue_name, limit=normalized_limit) if self.remediation_route_history_store is not None else ()
        return build_timeline_rows(plans=plans, executions=executions, route_history=route_history, limit=normalized_limit)

    def _build_data_freshness(self, *, monitor_report: Any, rollup_summary: Any, now: datetime) -> dict[str, Any]:
        return build_data_freshness(monitor_report=monitor_report, rollup_summary=rollup_summary, now=now)

    def _build_consistency_snapshot(self, *, monitor_report: Any, recent_alerts: Any, approval_preview: dict[str, Any], audit_preview: dict[str, Any], analytics_preview: Any, trend_preview: dict[str, Any], data_freshness: dict[str, Any]) -> dict[str, Any]:
        return build_consistency_snapshot(
            monitor_report=monitor_report,
            recent_alerts=recent_alerts,
            approval_preview=approval_preview,
            audit_preview=audit_preview,
            analytics_preview=analytics_preview,
            trend_preview=trend_preview,
            data_freshness=data_freshness,
        )

    def _build_trend_preview(self, *, tenant_id: str, queue_name: str, now: datetime) -> dict[str, Any]:
        if self.rollup_store is None:
            return {'window_count': 0, 'pending_direction': 'unknown', 'alert_churn': 'unknown'}
        windows = self.rollup_store.list_window_summaries(tenant_id=tenant_id, queue_name=queue_name, window_seconds=300, limit=6)
        if not windows:
            return {'window_count': 0, 'pending_direction': 'unknown', 'alert_churn': 'unknown'}
        latest = windows[-1]
        previous = windows[-2] if len(windows) > 1 else None
        pending_direction = 'flat'
        if previous is None:
            pending_direction = 'unknown'
        elif int(latest.max_pending_jobs) > int(previous.max_pending_jobs):
            pending_direction = 'up'
        elif int(latest.max_pending_jobs) < int(previous.max_pending_jobs):
            pending_direction = 'down'
        alert_churn = 'steady'
        if previous is None:
            alert_churn = 'unknown'
        elif int(latest.total_alert_count) > int(previous.total_alert_count):
            alert_churn = 'up'
        elif int(latest.total_alert_count) < int(previous.total_alert_count):
            alert_churn = 'down'
        return {
            'window_count': len(windows),
            'window_seconds': 300,
            'pending_direction': pending_direction,
            'alert_churn': alert_churn,
            'latest_pending_peak': int(latest.max_pending_jobs),
            'latest_alert_total': int(latest.total_alert_count),
            'latest_critical_alert_total': int(latest.total_critical_alert_count),
            'latest_status': str(latest.latest_status),
            'previous_pending_peak': None if previous is None else int(previous.max_pending_jobs),
            'previous_alert_total': None if previous is None else int(previous.total_alert_count),
            'fresh_window_age_seconds': None if not hasattr(latest, 'window_start_at') else max(0, int((now - latest.window_start_at).total_seconds())),
        }

    def _record_route_event(
        self,
        *,
        tenant_id: str,
        queue_name: str,
        action: str,
        source: str,
        status: str,
        metadata: dict[str, object],
        actor_id: str | None,
        request_id: str | None,
        now: datetime | None,
    ) -> None:
        if self.remediation_route_history_store is None:
            return
        self.remediation_route_history_store.record(
            tenant_id=normalize_tenant_id(tenant_id),
            queue_name=normalize_queue_name(queue_name),
            action=normalize_queue_name(action),
            source=normalize_source(source),
            actor_id=normalize_optional(actor_id),
            request_id=normalize_optional(request_id),
            status=normalize_queue_name(status),
            metadata=sanitize_metadata(metadata),
            recorded_at=now,
        )

    def _recent_alerts(self, *, tenant_id: str, queue_name: str, limit: int) -> tuple[QueueAlert, ...]:
        sink = self.alert_sink
        snapshot = getattr(sink, 'snapshot', None)
        if not callable(snapshot):
            return ()
        alerts = tuple(snapshot() or ())
        filtered = tuple(
            item
            for item in alerts
            if isinstance(item, QueueAlert)
            and str(item.tenant_id).strip() == str(tenant_id).strip()
            and str(item.queue_name).strip() == str(queue_name).strip()
        )
        ordered = tuple(sorted(filtered, key=lambda item: (item.created_at, str(item.code)), reverse=True))
        normalized_limit = normalize_limit(limit, default=20, upper=200)
        return ordered[:normalized_limit]


__all__ = [
    'CANON_API_QUEUE_OPS_ROUTE_HANDLERS',
    'QueueOpsRouteHandlers',
]

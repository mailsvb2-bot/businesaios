from __future__ import annotations

from datetime import datetime, timedelta, timezone, UTC

from runtime.queue.queue_remediation_analytics import QueueRemediationAnalyticsService
from runtime.queue.queue_remediation_audit_sqlite import SqliteQueueRemediationAuditStore
from runtime.queue.queue_remediation_hooks import (
    QueueRemediationCoordinator,
    QueueRemediationExecutionReport,
    QueueRemediationHook,
    QueueRemediationPlan,
)
from runtime.queue.queue_remediation_route_history_sqlite import SqliteQueueRemediationRouteHistoryStore


def test_queue_remediation_analytics_summarizes_activity(tmp_path):
    audit = SqliteQueueRemediationAuditStore(tmp_path / 'audit.sqlite3')
    routes = SqliteQueueRemediationRouteHistoryStore(tmp_path / 'routes.sqlite3')
    coordinator = QueueRemediationCoordinator(audit_sink=audit)
    now = datetime(2026, 3, 28, 12, 0, tzinfo=UTC)
    plan = QueueRemediationPlan(
        tenant_id='t1',
        queue_name='q1',
        generated_at=now,
        hooks=(
            QueueRemediationHook('t1', 'q1', 'run_janitor_tick', 'Run janitor', 'Recover', 'critical', category='recovery'),
            QueueRemediationHook('t1', 'q1', 'refresh_health_sample', 'Refresh health', 'Refresh', 'warning', category='verification'),
        ),
    )
    audit.record_plan(plan)
    audit.record_execution(
        QueueRemediationExecutionReport(
            tenant_id='t1',
            queue_name='q1',
            hook_code='run_janitor_tick',
            executed=True,
            reason='janitor_tick_executed',
            executed_at=now + timedelta(minutes=1),
            category='recovery',
            metadata={'safe_action': True},
        )
    )
    audit.record_execution(
        QueueRemediationExecutionReport(
            tenant_id='t1',
            queue_name='q1',
            hook_code='refresh_health_sample',
            executed=False,
            reason='review_required',
            executed_at=now + timedelta(minutes=2),
            category='verification',
            metadata={},
        )
    )
    routes.record(tenant_id='t1', queue_name='q1', action='get_queue_ops_view', source='control_plane', status='ok', recorded_at=now)
    routes.record(tenant_id='t1', queue_name='q1', action='execute_remediation_hook', source='control_plane', status='executed', recorded_at=now + timedelta(minutes=3))

    report = QueueRemediationAnalyticsService(audit_store=audit, route_history_store=routes).summarize(tenant_id='t1', queue_name='q1')

    assert report.plan_count == 1
    assert report.execution_count == 2
    assert report.executed_count == 1
    assert report.review_required_count == 1
    assert report.route_event_count == 2
    assert report.most_used_hook_code == 'refresh_health_sample' or report.most_used_hook_code == 'run_janitor_tick'
    assert report.most_used_action == 'execute_remediation_hook' or report.most_used_action == 'get_queue_ops_view'
    assert report.category_counts['recovery'] == 1
    assert report.category_counts['verification'] == 1
    assert report.reason_counts['janitor_tick_executed'] == 1


def test_queue_remediation_analytics_exposes_status_source_and_offer_gaps(tmp_path):
    audit = SqliteQueueRemediationAuditStore(tmp_path / 'audit2.sqlite3')
    routes = SqliteQueueRemediationRouteHistoryStore(tmp_path / 'routes2.sqlite3')
    now = datetime(2026, 3, 28, 14, 0, tzinfo=UTC)
    audit.record_plan(QueueRemediationPlan(tenant_id='t2', queue_name='q2', generated_at=now, hooks=(
        QueueRemediationHook('t2', 'q2', 'inspect_backpressure', 'Inspect', 'Inspect backlog', 'warning', category='inspection'),
        QueueRemediationHook('t2', 'q2', 'refresh_health_sample', 'Refresh', 'Refresh', 'warning', category='verification'),
    )))
    audit.record_execution(QueueRemediationExecutionReport(tenant_id='t2', queue_name='q2', hook_code='refresh_health_sample', executed=True, reason='health_refreshed', executed_at=now + timedelta(minutes=1), category='verification', metadata={}))
    routes.record(tenant_id='t2', queue_name='q2', action='get_queue_ops_view', source='web', status='ok', recorded_at=now)
    routes.record(tenant_id='t2', queue_name='q2', action='execute_remediation_hook', source='api', status='executed', recorded_at=now + timedelta(minutes=2))
    report = QueueRemediationAnalyticsService(audit_store=audit, route_history_store=routes).summarize(tenant_id='t2', queue_name='q2')
    assert report.source_counts['web'] == 1
    assert report.source_counts['api'] == 1
    assert report.status_counts['ok'] == 1
    assert report.status_counts['executed'] == 1
    assert report.hook_offer_counts['inspect_backpressure'] == 1
    assert report.top_unexecuted_hook_code == 'inspect_backpressure'
    assert report.execution_rate > 0



def test_queue_remediation_analytics_execution_rate_uses_executed_count(tmp_path):
    from datetime import datetime, timezone

    from runtime.queue.queue_remediation_analytics import QueueRemediationAnalyticsService
    from runtime.queue.queue_remediation_audit_sqlite import SqliteQueueRemediationAuditStore
    from runtime.queue.queue_remediation_hooks import (
        QueueRemediationExecutionReport,
        QueueRemediationHook,
        QueueRemediationPlan,
    )

    store = SqliteQueueRemediationAuditStore(path=tmp_path / 'audit.sqlite3')
    generated_at = datetime(2026, 1, 1, 0, 0, 0, tzinfo=UTC)
    store.record_plan(QueueRemediationPlan(tenant_id='tenant-a', queue_name='ops', hooks=(QueueRemediationHook(tenant_id='tenant-a', queue_name='ops', code='a', label='A', description='A', severity='warning'), QueueRemediationHook(tenant_id='tenant-a', queue_name='ops', code='b', label='B', description='B', severity='warning')), generated_at=generated_at))
    store.record_execution(QueueRemediationExecutionReport(tenant_id='tenant-a', queue_name='ops', hook_code='a', executed=True, reason='done', executed_at=generated_at, category='inspect'))
    store.record_execution(QueueRemediationExecutionReport(tenant_id='tenant-a', queue_name='ops', hook_code='b', executed=False, reason='review', executed_at=generated_at, category='review'))
    analytics = QueueRemediationAnalyticsService(audit_store=store).summarize(tenant_id='tenant-a', queue_name='ops')
    assert analytics.execution_rate == 0.5

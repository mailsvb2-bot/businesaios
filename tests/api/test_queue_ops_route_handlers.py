from __future__ import annotations

from datetime import UTC, datetime

from interfaces.api.queue_ops_route_handlers import QueueOpsRouteHandlers
from runtime.queue.job_contract import JobDispatchRequest
from runtime.queue.job_dispatcher import JobDispatcher
from runtime.queue.job_store import InMemoryJobStore
from runtime.queue.queue_alerts import QueueAlert


def test_queue_ops_route_handlers_build_view_and_audit(tmp_path):
    store = InMemoryJobStore()
    dispatcher = JobDispatcher(store=store)
    handlers = QueueOpsRouteHandlers(store=store)
    dispatcher.dispatch(JobDispatchRequest(tenant_id='tenant-a', job_id='job-1', queue_name='ops', job_type='demo', payload={}, dedupe_key='d1'))

    view = handlers.get_queue_ops_view(tenant_id='tenant-a', queue_name='ops', actor_id='operator-1', request_id='req-view', now=datetime(2026, 1, 1, 0, 0, 0, tzinfo=UTC))
    assert view['health']['status'] in {'critical', 'degraded', 'healthy'}
    assert view['remediation_plan']['hooks']
    assert view['audit_preview']['plan_count'] >= 1
    assert 'published_alert_count' in view['operator_summary']
    assert 'trend_preview' in view
    assert 'data_freshness' in view

    result = handlers.execute_remediation_hook(tenant_id='tenant-a', queue_name='ops', hook_code='open_queue_history', actor_id='operator-1', request_id='req-exec', now=datetime(2026, 1, 1, 0, 1, 0, tzinfo=UTC))
    assert result['executed'] is False

    audit = handlers.list_remediation_audit(tenant_id='tenant-a', queue_name='ops', actor_id='operator-1', request_id='req-audit')
    assert audit['plans']
    assert audit['executions']

    assert audit['route_history']
    assert audit['route_history'][0]['action']



def test_queue_ops_route_handlers_timeline_and_filters(tmp_path):
    store = InMemoryJobStore()
    dispatcher = JobDispatcher(store=store)
    handlers = QueueOpsRouteHandlers(store=store)
    dispatcher.dispatch(JobDispatchRequest(tenant_id='tenant-a', job_id='job-1', queue_name='ops', job_type='demo', payload={}, dedupe_key='d1'))

    view = handlers.get_queue_ops_view(tenant_id='tenant-a', queue_name='ops', actor_id='operator-1', request_id='req-view', now=datetime(2026, 1, 1, 0, 0, 0, tzinfo=UTC))
    assert view['timeline_preview']
    assert view['approval_preview']['approval_required_count'] >= 1

    handlers.execute_remediation_hook(tenant_id='tenant-a', queue_name='ops', hook_code='open_queue_history', actor_id='operator-1', request_id='req-exec', now=datetime(2026, 1, 1, 0, 1, 0, tzinfo=UTC))
    audit = handlers.list_remediation_audit(tenant_id='tenant-a', queue_name='ops', action='execute_remediation_hook', timeline_limit=5)
    assert audit['route_history']
    assert all(row['action'] == 'execute_remediation_hook' for row in audit['route_history'])
    assert len(audit['timeline']) <= 5


def test_queue_ops_route_handlers_redact_route_metadata(tmp_path):
    store = InMemoryJobStore()
    handlers = QueueOpsRouteHandlers(store=store)
    handlers._record_route_event(
        tenant_id='tenant-a',
        queue_name='ops',
        action='custom_event',
        actor_id='operator-1',
        request_id='req-secret',
        source='control_plane',
        status='ok',
        metadata={'authorization': 'Bearer very-secret-token', 'payload': 'x' * 400},
        now=datetime(2026, 1, 1, 0, 2, 0, tzinfo=UTC),
    )
    audit = handlers.list_remediation_audit(tenant_id='tenant-a', queue_name='ops', action='custom_event')
    assert audit['route_history'][0]['metadata']['authorization'] == '[redacted]'
    assert audit['route_history'][0]['metadata']['payload'].endswith('...')


def test_queue_ops_route_handlers_builds_evidence_timeline_and_consistency(tmp_path):
    store = InMemoryJobStore()
    dispatcher = JobDispatcher(store=store)
    handlers = QueueOpsRouteHandlers(store=store)
    dispatcher.dispatch(JobDispatchRequest(tenant_id='tenant-a', job_id='job-1', queue_name='ops', job_type='demo', payload={}, dedupe_key='d1'))
    view = handlers.get_queue_ops_view(tenant_id='tenant-a', queue_name='ops', now=datetime(2026, 1, 1, 0, 0, 0, tzinfo=UTC))
    assert view['evidence_timeline']
    entry_types = {row['entry_type'] for row in view['evidence_timeline']}
    assert 'health_sample' in entry_types
    assert 'remediation_plan' in entry_types
    assert view['consistency']['state'] in {'ok', 'warning', 'degraded'}
    assert view['operator_summary']['consistency_state'] == view['consistency']['state']


def test_queue_ops_route_handlers_staleness_consistency_degrades(tmp_path):
    store = InMemoryJobStore()
    handlers = QueueOpsRouteHandlers(store=store)
    now = datetime(2026, 1, 1, 0, 20, 0, tzinfo=UTC)
    stale_freshness = handlers._build_data_freshness(
        monitor_report=type('M', (), {'sampled_at': datetime(2026, 1, 1, 0, 0, 0, tzinfo=UTC)})(),
        rollup_summary=None,
        now=now,
    )
    consistency = handlers._build_consistency_snapshot(
        monitor_report=type('MR', (), {'alerts': (), 'slo': type('S', (), {'status': 'healthy'})()})(),
        recent_alerts=(),
        approval_preview={'approval_required_count': 0},
        audit_preview={'execution_count': 0, 'route_event_count': 0, 'plan_count': 0},
        analytics_preview=type('A', (), {'execution_count': 0, 'review_required_count': 0})(),
        trend_preview={'pending_direction': 'flat'},
        data_freshness=stale_freshness,
    )
    assert stale_freshness['state'] == 'stale'
    assert consistency['state'] == 'degraded'
    assert 'control_plane_data_stale' in consistency['issues']


def test_queue_ops_route_handlers_nested_payload_bounding(tmp_path):
    store = InMemoryJobStore()
    handlers = QueueOpsRouteHandlers(store=store)
    handlers._record_route_event(
        tenant_id='tenant-a', queue_name='ops', action='nested_event', actor_id='operator-1', request_id='req-nested', source='control_plane', status='ok',
        metadata={'payload': {'authorization': 'secret', 'items': [{'token': 'abc', 'value': 'x' * 500}] * 20}},
        now=datetime(2026, 1, 1, 0, 2, 0, tzinfo=UTC),
    )
    audit = handlers.list_remediation_audit(tenant_id='tenant-a', queue_name='ops', action='nested_event')
    payload = audit['route_history'][0]['metadata']['payload']
    assert payload['authorization'] == '[redacted]'
    assert payload['items'][-1] == '[truncated]'
    assert payload['items'][0]['token'] == '[redacted]'



def test_queue_ops_route_handlers_recent_alerts_are_latest_first(tmp_path):
    store = InMemoryJobStore()
    handlers = QueueOpsRouteHandlers(store=store)
    handlers.alert_sink.publish((
        QueueAlert(tenant_id='tenant-a', queue_name='ops', code='older', severity='warning', message='older', created_at=datetime(2026, 1, 1, 0, 0, 0, tzinfo=UTC)),
        QueueAlert(tenant_id='tenant-a', queue_name='ops', code='newer', severity='warning', message='newer', created_at=datetime(2026, 1, 1, 0, 1, 0, tzinfo=UTC)),
    ))
    recent = handlers._recent_alerts(tenant_id='tenant-a', queue_name='ops', limit=2)
    assert [item.code for item in recent] == ['newer', 'older']


def test_queue_ops_route_handlers_route_event_normalizes_fields(tmp_path):
    store = InMemoryJobStore()
    handlers = QueueOpsRouteHandlers(store=store)
    handlers._record_route_event(
        tenant_id='tenant-a',
        queue_name='ops',
        action=' custom_event ',
        actor_id=' operator-1 ',
        request_id=' req-1 ',
        source=' ',
        status=' ok ',
        metadata={'': 'value'},
        now=datetime(2026, 1, 1, 0, 2, 0, tzinfo=UTC),
    )
    audit = handlers.list_remediation_audit(tenant_id='tenant-a', queue_name='ops', action='custom_event')
    assert audit['route_history'][0]['source'] == 'control_plane'
    assert audit['route_history'][0]['metadata']['_'] == 'value'


def test_queue_ops_route_handlers_route_metadata_datetime_and_set_are_sanitized(tmp_path):
    store = InMemoryJobStore()
    handlers = QueueOpsRouteHandlers(store=store)
    handlers._record_route_event(
        tenant_id='tenant-a',
        queue_name='ops',
        action='set_event',
        actor_id='operator-1',
        request_id='req-set',
        source='control_plane',
        status='ok',
        metadata={'seen_at': datetime(2026, 1, 1, 0, 2, 0, tzinfo=UTC), 'items': {'b', 'a'}},
        now=datetime(2026, 1, 1, 0, 2, 0, tzinfo=UTC),
    )
    audit = handlers.list_remediation_audit(tenant_id='tenant-a', queue_name='ops', action='set_event')
    assert audit['route_history'][0]['metadata']['seen_at'].startswith('2026-01-01T00:02:00')
    assert audit['route_history'][0]['metadata']['items'] == ('a', 'b')



def test_queue_ops_route_handlers_normalize_actor_and_request_fields(tmp_path):
    store = InMemoryJobStore()
    handlers = QueueOpsRouteHandlers(store=store)
    handlers._record_route_event(
        tenant_id='tenant-a',
        queue_name='ops',
        action='custom_event',
        actor_id='  ',
        request_id=' req-1 ',
        source='control plane',
        status='ok',
        metadata={'session_token': 'very-secret'},
        now=datetime(2026, 1, 1, 0, 3, 0, tzinfo=UTC),
    )
    audit = handlers.list_remediation_audit(tenant_id='tenant-a', queue_name='ops', action='custom_event')
    row = audit['route_history'][0]
    assert row['actor_id'] is None
    assert row['request_id'] == 'req-1'
    assert row['source'] == 'control_plane'
    assert row['metadata']['session_token'] == '[redacted]'

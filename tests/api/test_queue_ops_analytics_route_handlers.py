from __future__ import annotations

from interfaces.api.queue_ops_route_handlers import QueueOpsRouteHandlers


def test_queue_ops_route_handlers_return_remediation_analytics(tmp_path, monkeypatch):
    monkeypatch.setenv('BUSINESAIOS_QUEUE_METRICS_ROLLUP_SQLITE_PATH', str(tmp_path / 'rollup.sqlite3'))
    monkeypatch.setenv('BUSINESAIOS_QUEUE_REMEDIATION_AUDIT_SQLITE_PATH', str(tmp_path / 'audit.sqlite3'))
    monkeypatch.setenv('BUSINESAIOS_QUEUE_REMEDIATION_ROUTE_HISTORY_SQLITE_PATH', str(tmp_path / 'route.sqlite3'))
    handlers = QueueOpsRouteHandlers()
    handlers.get_queue_ops_view(tenant_id='t1', queue_name='q1')
    handlers.list_remediation_audit(tenant_id='t1', queue_name='q1')
    analytics = handlers.get_remediation_analytics(tenant_id='t1', queue_name='q1')

    assert analytics['tenant_id'] == 't1'
    assert analytics['queue_name'] == 'q1'
    assert analytics['analytics']['route_event_count'] >= 2
    assert analytics['analytics']['most_used_action'] in {'get_queue_ops_view', 'list_remediation_audit', 'get_remediation_analytics'}


def test_queue_ops_view_returns_analytics_preview(tmp_path, monkeypatch):
    monkeypatch.setenv('BUSINESAIOS_QUEUE_METRICS_ROLLUP_SQLITE_PATH', str(tmp_path / 'rollup2.sqlite3'))
    monkeypatch.setenv('BUSINESAIOS_QUEUE_REMEDIATION_AUDIT_SQLITE_PATH', str(tmp_path / 'audit2.sqlite3'))
    monkeypatch.setenv('BUSINESAIOS_QUEUE_REMEDIATION_ROUTE_HISTORY_SQLITE_PATH', str(tmp_path / 'route2.sqlite3'))
    handlers = QueueOpsRouteHandlers()
    payload = handlers.get_queue_ops_view(tenant_id='t1', queue_name='q1')
    assert payload['analytics_preview'] is not None
    assert 'execution_rate' in payload['analytics_preview']
    assert payload['audit_preview'] is not None
    assert payload['operator_summary']['audit_execution_count'] >= 0

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from runtime.queue.queue_remediation_audit_postgres import PostgresQueueRemediationAuditStore
from runtime.queue.queue_remediation_hooks import (
    QueueRemediationExecutionReport,
    QueueRemediationHook,
    QueueRemediationPlan,
)
from runtime.queue.queue_remediation_route_history_postgres import PostgresQueueRemediationRouteHistoryStore


@dataclass
class _SharedDb:
    plans: list[tuple] = None
    executions: list[tuple] = None
    routes: list[tuple] = None

    def __post_init__(self):
        self.plans = [] if self.plans is None else self.plans
        self.executions = [] if self.executions is None else self.executions
        self.routes = [] if self.routes is None else self.routes


class FakePostgresPort:
    shared = _SharedDb()

    def __init__(self, dsn: str, application_name: str = 'test'):
        self.dsn = dsn
        self.application_name = application_name

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return None

    def execute(self, sql, params=None):
        q = ' '.join(str(sql).split()).lower()
        if 'insert into runtime_queue_remediation_plan_audit' in q:
            self.shared.plans.append(tuple(params))
        elif 'insert into runtime_queue_remediation_execution_audit' in q:
            self.shared.executions.append(tuple(params))
        elif 'insert into runtime_queue_remediation_route_history' in q:
            self.shared.routes.append(tuple(params))

    def fetchall(self, sql, params=None):
        q = ' '.join(str(sql).split()).lower()
        tenant_id, queue_name, limit = params
        if 'from runtime_queue_remediation_plan_audit' in q:
            rows = [row for row in self.shared.plans if row[0] == tenant_id and row[1] == queue_name]
            return list(reversed(rows))[:limit]
        if 'from runtime_queue_remediation_execution_audit' in q:
            rows = [row for row in self.shared.executions if row[0] == tenant_id and row[1] == queue_name]
            return list(reversed(rows))[:limit]
        if 'from runtime_queue_remediation_route_history' in q:
            rows = [row for row in self.shared.routes if row[0] == tenant_id and row[1] == queue_name]
            return list(reversed(rows))[:limit]
        return []

    def commit(self):
        return None


def test_postgres_queue_remediation_stores_roundtrip(monkeypatch):
    monkeypatch.setattr('runtime.queue.queue_remediation_audit_postgres.PostgresPort', FakePostgresPort)
    monkeypatch.setattr('runtime.queue.queue_remediation_route_history_postgres.PostgresPort', FakePostgresPort)
    FakePostgresPort.shared = _SharedDb()
    now = datetime(2026, 3, 28, 12, 0, tzinfo=UTC)

    with PostgresQueueRemediationAuditStore('postgres://example') as audit, PostgresQueueRemediationRouteHistoryStore('postgres://example') as routes:
        audit.record_plan(
            QueueRemediationPlan(
                tenant_id='t1',
                queue_name='q1',
                generated_at=now,
                hooks=(QueueRemediationHook('t1', 'q1', 'refresh_health_sample', 'Refresh', 'Refresh', 'warning'),),
            )
        )
        audit.record_execution(
            QueueRemediationExecutionReport(
                tenant_id='t1',
                queue_name='q1',
                hook_code='refresh_health_sample',
                executed=True,
                reason='health_sample_refreshed',
                executed_at=now,
            )
        )
        routes.record(tenant_id='t1', queue_name='q1', action='get_queue_ops_view', source='control_plane', status='ok', metadata={'x': 1}, recorded_at=now)

        assert len(audit.list_plan_entries(tenant_id='t1', queue_name='q1')) == 1
        assert len(audit.list_execution_entries(tenant_id='t1', queue_name='q1')) == 1
        route = routes.list_entries(tenant_id='t1', queue_name='q1')[0]
        assert route.action == 'get_queue_ops_view'
        assert route.metadata['x'] == 1

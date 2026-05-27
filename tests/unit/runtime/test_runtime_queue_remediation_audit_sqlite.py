from __future__ import annotations

from datetime import datetime, timezone

from runtime.queue.queue_remediation_audit_sqlite import SqliteQueueRemediationAuditStore
from runtime.queue.queue_remediation_hooks import (
    QueueRemediationCoordinator,
    QueueRemediationHook,
    QueueRemediationPlan,
)
from runtime.queue.queue_slo import QueueSLOReport


def test_runtime_queue_remediation_audit_store_records_plan_and_execution(tmp_path):
    store = SqliteQueueRemediationAuditStore(path=tmp_path / 'remediation_audit.sqlite3')
    coordinator = QueueRemediationCoordinator(audit_sink=store)
    report = QueueSLOReport(
        tenant_id='tenant-a',
        queue_name='ops',
        ok=False,
        status='critical',
        reasons=('leadership_stale',),
        pending_jobs=0,
        active_claims=0,
        dead_letter_jobs=0,
        janitor_stale_seconds=1,
        leader_stale_seconds=130,
    )
    plan = coordinator.plan(report=report, alerts=(), now=datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc))
    assert plan.hooks
    execution = coordinator.execute(tenant_id='tenant-a', queue_name='ops', hook_code='open_queue_history', now=datetime(2026, 1, 1, 0, 1, 0, tzinfo=timezone.utc))
    assert execution.executed is False

    plans = store.list_plan_entries(tenant_id='tenant-a', queue_name='ops')
    executions = store.list_execution_entries(tenant_id='tenant-a', queue_name='ops')
    assert len(plans) == 1
    assert plans[0].hooks[0]['code']
    assert len(executions) == 1
    assert executions[0].hook_code == 'open_queue_history'
    assert executions[0].reason == 'operator_review_required'

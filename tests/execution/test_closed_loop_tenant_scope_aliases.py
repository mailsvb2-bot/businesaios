import pytest

from execution.closed_loop_orchestrator import ClosedLoopOrchestrator


def test_closed_loop_accepts_tenant_queue_scope_alias():
    orchestrator = ClosedLoopOrchestrator()
    scope = {"tenant_id": "tenant-a", "queue_name": "main", "namespace": "runtime", "scope_key": "tenant/tenant-a/runtime/queue/main"}
    resolved = orchestrator._tenant_scope_for(action={"tenant_queue_scope": scope}, execution_receipt={})
    assert resolved is not None
    assert resolved.scope_key == scope['scope_key']


def test_closed_loop_rejects_mismatched_declared_scope_key():
    orchestrator = ClosedLoopOrchestrator()
    with pytest.raises(ValueError):
        orchestrator._assert_tenant_consistency(
            action={"tenant_id": "tenant-a", "queue_name": "main", "tenant_queue_scope": {"tenant_id": "tenant-a", "queue_name": "main", "namespace": "runtime", "scope_key": "tenant/tenant-a/runtime/queue/other"}},
            execution_receipt={},
        )

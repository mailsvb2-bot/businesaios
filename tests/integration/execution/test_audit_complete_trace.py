from __future__ import annotations

from dataclasses import dataclass

from entrypoints.api.request_context import RequestContext
from governance.control_plane_audit_log import GovernanceAuditEvent, PersistentGovernanceAuditLog
from infra.feature_flag_store import InMemoryFeatureFlagStore
from infra.feature_flags import FeatureFlags
from infra.kill_switches import KillSwitchRegistry
from infra.maintenance_mode import MaintenanceMode
from infra.runtime_guardrails import RuntimeGuardrails
from interfaces.api.action_models import ExecuteActionRequest, ExecuteActionResponse
from interfaces.api.execute_action_with_control_plane import ExecuteActionWithControlPlane
from observability.action_audit_log import ActionAuditLog
from tenancy.tenant_audit_scope import TenantAuditScope
from tenancy.tenant_billing_scope import TenantBillingScope
from tenancy.tenant_connector_scope import TenantConnectorScope
from tenancy.tenant_feature_flags import TenantFeatureFlags
from tenancy.tenant_memory_scope import TenantMemoryScope
from tenancy.tenant_policy_store import InMemoryTenantPolicyStore, TenantPolicyBundle
from tenancy.tenant_quota_guard import TenantQuotaGuard
from tenancy.tenant_runtime_limits import TenantRuntimeLimits


@dataclass
class _Handler:
    def handle(self, request: ExecuteActionRequest) -> ExecuteActionResponse:
        return ExecuteActionResponse(status='ok', action_type=request.action_type, reason='executed')


def _guardrails() -> RuntimeGuardrails:
    flags = FeatureFlags(store=InMemoryFeatureFlagStore())
    flags.enable('api.execute_action.enabled')
    return RuntimeGuardrails(feature_flags=flags, kill_switches=KillSwitchRegistry(), maintenance_mode=MaintenanceMode())


def _bundle(tenant_id: str) -> TenantPolicyBundle:
    return TenantPolicyBundle(
        tenant_id=tenant_id,
        feature_flags=TenantFeatureFlags(tenant_id=tenant_id),
        runtime_limits=TenantRuntimeLimits(tenant_id=tenant_id),
        memory_scope=TenantMemoryScope(tenant_id=tenant_id),
        connector_scope=TenantConnectorScope(tenant_id=tenant_id, require_explicit_allowlist=False),
        audit_scope=TenantAuditScope(tenant_id=tenant_id),
        billing_scope=TenantBillingScope(tenant_id=tenant_id),
        quotas={'actions_per_hour': 1},
    )


def test_audit_complete_trace_covers_runtime_and_governance_layers(tmp_path) -> None:
    runtime_audit = ActionAuditLog()
    governance_audit = PersistentGovernanceAuditLog(tmp_path / 'governance_audit.jsonl')
    store = InMemoryTenantPolicyStore()
    store.save(_bundle('tenant-a'))

    wrapper = ExecuteActionWithControlPlane(
        handler=_Handler(),
        guardrails=_guardrails(),
        tenant_quota_guard=TenantQuotaGuard(policy_store=store),
        action_audit_log=runtime_audit,
    )
    response = wrapper.handle(
        request=ExecuteActionRequest(action_type='sync_crm', payload={'tenant_id': 'tenant-a', 'action_id': 'audit-1'}),
        request_context=RequestContext(tenant_id='tenant-a', correlation_id='trace-123', request_id='req-123'),
    )
    governance_audit.append(GovernanceAuditEvent(event_type='tenant_policy_reviewed', tenant_id='tenant-a', payload={'trace_id': 'trace-123'}))
    governance_audit.validate_chain()

    trace_records = runtime_audit.list_by_trace(trace_id='trace-123')

    assert response.status == 'ok'
    assert len(trace_records) == 3
    assert trace_records[0]['payload']['stage'] == 'control_plane.executed'
    assert governance_audit.read_events()[0]['payload']['trace_id'] == 'trace-123'


def test_audit_complete_trace_chain_detects_tampering(tmp_path) -> None:
    governance_audit = PersistentGovernanceAuditLog(tmp_path / 'governance_audit.jsonl')
    governance_audit.append(GovernanceAuditEvent(event_type='evt1', tenant_id='tenant-a', payload={'x': 1}))
    governance_audit.append(GovernanceAuditEvent(event_type='evt2', tenant_id='tenant-a', payload={'x': 2}))
    items = list(governance_audit.read_events())
    tampered = dict(items[1])
    tampered['payload'] = {'x': 999}
    governance_audit.path.write_text('\n'.join([
        __import__('json').dumps(items[0], ensure_ascii=False, sort_keys=True),
        __import__('json').dumps(tampered, ensure_ascii=False, sort_keys=True),
    ]) + '\n', encoding='utf-8')

    import pytest
    with pytest.raises(ValueError, match='record_hash mismatch'):
        governance_audit.validate_chain()

from __future__ import annotations

from dataclasses import dataclass

from interfaces.api.admin_route_handlers import AdminRouteHandlers
from reliability.execution_reconciliation import ReconciliationReport
from reliability.outbox_store import OutboxMessage, OutboxState
from reliability.recovery_orchestrator import RecoveryPlan, TransportRecoveryResult
from tenancy.tenant_audit_scope import TenantAuditScope
from tenancy.tenant_billing_scope import TenantBillingScope
from tenancy.tenant_connector_scope import TenantConnectorScope
from tenancy.tenant_contract import TenantRecord
from tenancy.tenant_feature_flags import TenantFeatureFlags
from tenancy.tenant_memory_scope import TenantMemoryScope
from tenancy.tenant_policy_store import InMemoryTenantPolicyStore, TenantPolicyBundle
from tenancy.tenant_registry import InMemoryTenantRegistry
from tenancy.tenant_runtime_limits import TenantRuntimeLimits


@dataclass(frozen=True)
class _Run:
    run_id: str = 'run-1'
    trace_id: str = 'trace-1'
    status: str = 'running'
    stage: str = 'execution'


def test_admin_route_handlers_build_operator_views() -> None:
    handlers = AdminRouteHandlers(
        tenant_registry=InMemoryTenantRegistry((TenantRecord(tenant_id='tenant-default', display_name='Default Tenant'),)),
        tenant_policy_store=InMemoryTenantPolicyStore((
            TenantPolicyBundle(
                tenant_id='tenant-default',
                feature_flags=TenantFeatureFlags(tenant_id='tenant-default'),
                runtime_limits=TenantRuntimeLimits(tenant_id='tenant-default', max_daily_budget=100.0),
                memory_scope=TenantMemoryScope(tenant_id='tenant-default'),
                connector_scope=TenantConnectorScope(tenant_id='tenant-default', require_explicit_allowlist=False),
                audit_scope=TenantAuditScope(tenant_id='tenant-default'),
                billing_scope=TenantBillingScope(tenant_id='tenant-default'),
                quotas={'actions_per_day': 10.0},
            ),
        )),
    )
    plan = RecoveryPlan(
        run_id='run-1',
        recovery_action='resume',
        reason='checkpoint present',
        reconciliation=ReconciliationReport(
            run_id='run-1', latest_stage='execution', idempotency_state='running', outbox_state='pending', checkpoint_count=1
        ),
    )
    run_view = handlers.get_operator_run_view(tenant_id='tenant-default', run_snapshot=_Run(), allowed_controls=('resume',), recent_events=())
    assert run_view['run']['run_id'] == 'run-1'
    dead_view = handlers.get_dead_letter_view(
        tenant_id='tenant-default',
        entries=(OutboxMessage(tenant_id='tenant-default', message_id='m1', topic='mail', dedupe_key='d1', payload={}, state=OutboxState.DEAD),),
    )
    assert dead_view['count'] == 1
    recovery_view = handlers.get_recovery_view(
        tenant_id='tenant-default',
        plan=plan,
        transport_results=(TransportRecoveryResult('smtp', 'worker-1', 'smtp', 1, 1, 0, 0, 0),),
    )
    assert recovery_view['plan']['recovery_action'] == 'resume'
    budget_view = handlers.get_autonomy_budget_view(tenant_id='tenant-default', usage_payload={'action_count': 1})
    assert budget_view['tenant_id'] == 'tenant-default'
    assert budget_view['verdict']['tenant_id'] == 'tenant-default'

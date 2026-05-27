from interfaces.api.inference_runtime_admin_route_handlers import InferenceRuntimeAdminRouteHandlers
from observability.action_audit_log import ActionAuditLog
from observability.inference_budget_burn_log import InferenceBudgetBurnLog
from observability.inference_escalation_audit_log import InferenceEscalationAuditLog
from observability.inference_runtime_summary import InferenceRuntimeSummaryService
from runtime.inference.providers.cpu_fallback_provider import CPUFallbackProvider
from runtime.inference.providers.local_gpu_provider import LocalGPUProvider
from runtime.inference.providers.provider_health_monitor import InferenceProviderHealthMonitor
from runtime.inference.provisioning.capacity_state_store import InferenceCapacityStateStore


def test_inference_runtime_admin_routes_expose_richer_payload():
    monitor = InferenceProviderHealthMonitor(
        providers={
            'cpu_fallback_provider': CPUFallbackProvider(),
            'local_gpu_provider': LocalGPUProvider(),
        }
    )
    action_audit_log = ActionAuditLog()
    action_audit_log.record_inference_selection(
        tenant_id='tenant-a',
        action_id='a1',
        action_type='send_message',
        provider_name='local_gpu_provider',
        capacity_tier='local_gpu',
        estimated_cost_usd=0.25,
    )
    action_audit_log.record_inference_verification(
        tenant_id='tenant-a',
        action_id='a1',
        action_type='send_message',
        provider_name='local_gpu_provider',
        accepted=True,
        verification_reason='accepted',
    )
    summary = InferenceRuntimeSummaryService(
        state_store=InferenceCapacityStateStore(),
        provider_health_monitor=monitor,
        escalation_audit_log=InferenceEscalationAuditLog(),
        budget_burn_log=InferenceBudgetBurnLog(),
        action_audit_log=action_audit_log,
    )
    handlers = InferenceRuntimeAdminRouteHandlers(summary)
    payload = handlers.get_runtime_admin_payload(tenant_id='tenant-a')
    assert payload['tenant_id'] == 'tenant-a'
    assert 'verification_summary' in payload
    assert 'recent_escalations' in payload
    assert 'total_estimated_cost_usd' in payload

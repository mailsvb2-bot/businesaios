from observability.action_audit_log import ActionAuditLog
from observability.inference_acceleration_log import InferenceAccelerationLog
from observability.inference_budget_burn_log import InferenceBudgetBurnLog
from observability.inference_escalation_audit_log import InferenceEscalationAuditLog
from observability.inference_runtime_summary import InferenceRuntimeSummaryService
from interfaces.api.inference_runtime_admin_route_handlers import InferenceRuntimeAdminRouteHandlers
from runtime.inference.provisioning.capacity_state_store import InferenceCapacityStateStore
from runtime.inference.providers.cpu_fallback_provider import CPUFallbackProvider
from runtime.inference.providers.local_gpu_provider import LocalGPUProvider
from runtime.inference.providers.provider_health_monitor import InferenceProviderHealthMonitor


def test_inference_runtime_admin_routes_expose_acceleration_summary():
    monitor = InferenceProviderHealthMonitor(
        providers={
            'cpu_fallback_provider': CPUFallbackProvider(),
            'local_gpu_provider': LocalGPUProvider(),
        }
    )
    acceleration_log = InferenceAccelerationLog()
    acceleration_log.record(
        tenant_id='tenant-a',
        provider_name='local_gpu_provider',
        tier='local_gpu',
        execution_mode='accelerated',
        device_class='local_gpu',
        transport_kind='pci_local',
        prefers_local_memory=True,
        batch_items=4,
        provider_max_batch_items=16,
        expected_transfer_overhead_ms=2,
    )
    summary = InferenceRuntimeSummaryService(
        state_store=InferenceCapacityStateStore(),
        provider_health_monitor=monitor,
        escalation_audit_log=InferenceEscalationAuditLog(),
        budget_burn_log=InferenceBudgetBurnLog(),
        action_audit_log=ActionAuditLog(),
        acceleration_log=acceleration_log,
    )
    handlers = InferenceRuntimeAdminRouteHandlers(summary)
    payload = handlers.get_runtime_admin_payload(tenant_id='tenant-a')
    assert 'acceleration_summary' in payload
    assert payload['acceleration_summary']['event_count'] == 1

from observability.action_audit_log import ActionAuditLog
from observability.inference_budget_burn_log import InferenceBudgetBurnLog
from observability.inference_escalation_audit_log import InferenceEscalationAuditLog
from observability.inference_runtime_summary import InferenceRuntimeSummaryService
from runtime.inference.providers.cpu_fallback_provider import CPUFallbackProvider
from runtime.inference.providers.local_gpu_provider import LocalGPUProvider
from runtime.inference.providers.provider_health_monitor import InferenceProviderHealthMonitor
from runtime.inference.provisioning.capacity_state_store import InferenceCapacityStateStore


def test_inference_runtime_summary_builds_operator_snapshot():
    state_store = InferenceCapacityStateStore()
    monitor = InferenceProviderHealthMonitor(
        providers={
            'cpu_fallback_provider': CPUFallbackProvider(),
            'local_gpu_provider': LocalGPUProvider(),
        }
    )
    audit_log = InferenceEscalationAuditLog()
    action_audit_log = ActionAuditLog()
    action_audit_log.record_inference_selection(
        tenant_id='tenant-a',
        action_id='a1',
        action_type='send_message',
        provider_name='local_gpu_provider',
        capacity_tier='local_gpu',
        estimated_cost_usd=1.5,
    )
    action_audit_log.record_inference_verification(
        tenant_id='tenant-a',
        action_id='a1',
        action_type='send_message',
        provider_name='local_gpu_provider',
        accepted=True,
        verification_reason='accepted',
    )
    audit_log.record(from_tier='cpu_fallback', to_tier='local_gpu', reason='pressure')
    budget_log = InferenceBudgetBurnLog()
    budget_log.record(
        tenant_id='tenant-a',
        provider_name='local_gpu_provider',
        tier='local_gpu',
        estimated_cost_usd=1.5,
    )
    service = InferenceRuntimeSummaryService(
        state_store=state_store,
        provider_health_monitor=monitor,
        escalation_audit_log=audit_log,
        budget_burn_log=budget_log,
        action_audit_log=action_audit_log,
    )
    payload = service.build()
    assert payload['active_tier'] == 'local_gpu'
    assert len(payload['providers']) == 2
    assert payload['burn_rate_usd_per_hour'] == 1.5
    assert payload['provider_mix'][0]['provider_name'] == 'local_gpu_provider'
    assert payload['verification_summary']['accepted_count'] == 1
    assert payload['escalation_event_count'] == 1

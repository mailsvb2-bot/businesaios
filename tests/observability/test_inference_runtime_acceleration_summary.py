from observability.action_audit_log import ActionAuditLog
from observability.inference_acceleration_log import InferenceAccelerationLog
from observability.inference_budget_burn_log import InferenceBudgetBurnLog
from observability.inference_escalation_audit_log import InferenceEscalationAuditLog
from observability.inference_runtime_summary import InferenceRuntimeSummaryService
from runtime.inference.provisioning.capacity_state_store import InferenceCapacityStateStore
from runtime.inference.providers.cpu_fallback_provider import CPUFallbackProvider
from runtime.inference.providers.local_gpu_provider import LocalGPUProvider
from runtime.inference.providers.provider_health_monitor import InferenceProviderHealthMonitor


def test_inference_runtime_summary_includes_acceleration_mix():
    state_store = InferenceCapacityStateStore()
    monitor = InferenceProviderHealthMonitor(
        providers={
            "cpu_fallback_provider": CPUFallbackProvider(),
            "local_gpu_provider": LocalGPUProvider(),
        }
    )
    audit_log = InferenceEscalationAuditLog()
    budget_log = InferenceBudgetBurnLog()
    action_audit_log = ActionAuditLog()
    acceleration_log = InferenceAccelerationLog()
    acceleration_log.record(
        tenant_id="tenant-a",
        provider_name="local_gpu_provider",
        tier="local_gpu",
        execution_mode="accelerated",
        transport_kind="pci_local",
        batch_items=8,
        expected_transfer_overhead_ms=2,
    )
    acceleration_log.record(
        tenant_id="tenant-a",
        provider_name="local_gpu_provider",
        tier="local_gpu",
        execution_mode="accelerated",
        transport_kind="pci_local",
        batch_items=4,
        expected_transfer_overhead_ms=2,
    )
    service = InferenceRuntimeSummaryService(
        state_store=state_store,
        provider_health_monitor=monitor,
        escalation_audit_log=audit_log,
        budget_burn_log=budget_log,
        action_audit_log=action_audit_log,
        acceleration_log=acceleration_log,
    )
    payload = service.build(tenant_id="tenant-a")
    summary = payload["acceleration_summary"]
    assert summary["event_count"] == 2
    assert summary["execution_mode_mix"][0]["execution_mode"] == "accelerated"
    assert summary["transport_kind_mix"][0]["transport_kind"] == "pci_local"
    assert summary["average_batch_items"] == 6.0
    assert summary["average_transfer_overhead_ms"] == 2.0

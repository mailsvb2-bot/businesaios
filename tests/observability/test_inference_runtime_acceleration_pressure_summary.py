from observability.action_audit_log import ActionAuditLog
from observability.inference_acceleration_log import InferenceAccelerationLog
from observability.inference_budget_burn_log import InferenceBudgetBurnLog
from observability.inference_escalation_audit_log import InferenceEscalationAuditLog
from observability.inference_runtime_summary import InferenceRuntimeSummaryService
from runtime.inference.provisioning.capacity_state_store import InferenceCapacityStateStore
from runtime.inference.providers.cpu_fallback_provider import CPUFallbackProvider
from runtime.inference.providers.local_gpu_provider import LocalGPUProvider
from runtime.inference.providers.provider_health_monitor import InferenceProviderHealthMonitor


def test_inference_runtime_summary_includes_acceleration_pressure_and_locality_mix():
    state_store = InferenceCapacityStateStore()
    monitor = InferenceProviderHealthMonitor(
        providers={
            "cpu_fallback_provider": CPUFallbackProvider(),
            "local_gpu_provider": LocalGPUProvider(),
        }
    )
    acceleration_log = InferenceAccelerationLog()
    acceleration_log.record(
        tenant_id="tenant-a",
        provider_name="local_gpu_provider",
        tier="local_gpu",
        execution_mode="accelerated",
        device_class="local_gpu",
        transport_kind="pci_local",
        prefers_local_memory=True,
        batch_items=8,
        provider_max_batch_items=16,
        expected_transfer_overhead_ms=2,
    )
    acceleration_log.record(
        tenant_id="tenant-a",
        provider_name="local_gpu_provider",
        tier="local_gpu",
        execution_mode="accelerated",
        device_class="local_gpu",
        transport_kind="pci_local",
        prefers_local_memory=True,
        batch_items=16,
        provider_max_batch_items=16,
        expected_transfer_overhead_ms=3,
    )
    service = InferenceRuntimeSummaryService(
        state_store=state_store,
        provider_health_monitor=monitor,
        escalation_audit_log=InferenceEscalationAuditLog(),
        budget_burn_log=InferenceBudgetBurnLog(),
        action_audit_log=ActionAuditLog(),
        acceleration_log=acceleration_log,
    )
    payload = service.build(tenant_id="tenant-a")
    summary = payload["acceleration_summary"]
    assert summary["device_class_mix"][0]["device_class"] == "local_gpu"
    assert summary["local_memory_preference_mix"][0]["memory_preference"] == "local"
    assert summary["provider_batch_utilization_mix"][0]["utilization_band"] == "high"
    assert summary["average_batch_utilization_ratio"] == 0.75

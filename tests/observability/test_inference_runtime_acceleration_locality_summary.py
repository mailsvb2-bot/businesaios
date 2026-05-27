from observability.action_audit_log import ActionAuditLog
from observability.inference_acceleration_log import InferenceAccelerationLog
from observability.inference_budget_burn_log import InferenceBudgetBurnLog
from observability.inference_escalation_audit_log import InferenceEscalationAuditLog
from observability.inference_runtime_summary import InferenceRuntimeSummaryService
from runtime.inference.providers.cpu_fallback_provider import CPUFallbackProvider
from runtime.inference.providers.local_gpu_provider import LocalGPUProvider
from runtime.inference.providers.provider_health_monitor import InferenceProviderHealthMonitor
from runtime.inference.provisioning.capacity_state_store import InferenceCapacityStateStore


def test_inference_runtime_summary_includes_pressure_and_locality_mix():
    state_store = InferenceCapacityStateStore()
    monitor = InferenceProviderHealthMonitor(
        providers={
            "cpu_fallback_provider": CPUFallbackProvider(),
            "local_gpu_provider": LocalGPUProvider(),
        }
    )
    log = InferenceAccelerationLog()
    log.record(
        tenant_id="tenant-a",
        provider_name="local_gpu_provider",
        tier="local_gpu",
        execution_mode="accelerated",
        device_class="local_gpu",
        transport_kind="pci_local",
        prefers_local_memory=True,
        batch_items=8,
        provider_max_batch_items=16,
        expected_transfer_overhead_ms=3,
        saturation_score=0.72,
        pressure_band="high",
        locality_scope="local",
        expected_queue_penalty_ms=5,
    )
    service = InferenceRuntimeSummaryService(
        state_store=state_store,
        provider_health_monitor=monitor,
        escalation_audit_log=InferenceEscalationAuditLog(),
        budget_burn_log=InferenceBudgetBurnLog(),
        action_audit_log=ActionAuditLog(),
        acceleration_log=log,
    )
    payload = service.build(tenant_id="tenant-a")
    summary = payload["acceleration_summary"]
    assert summary["pressure_band_mix"][0]["pressure_band"] == "high"
    assert summary["locality_scope_mix"][0]["locality_scope"] == "local"
    assert summary["average_saturation_score"] == 0.72
    assert summary["average_expected_queue_penalty_ms"] == 5.0

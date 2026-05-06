from execution.inference_capacity_contract import InferenceCapacityTier
from execution.inference_acceleration_contract import InferenceAccelerationProfile, InferenceMemoryTransferPlan
from execution.inference_provider_contract import InferenceProviderHealth
from runtime.inference.providers.provider_acceleration_pressure_policy import ProviderAccelerationPressurePolicy


def test_provider_acceleration_pressure_policy_normalizes_pressure_and_locality():
    policy = ProviderAccelerationPressurePolicy()
    plan = policy.plan(
        profile=InferenceAccelerationProfile(
            tier=InferenceCapacityTier.LOCAL_GPU,
            execution_mode="accelerated",
            device_class="local_gpu",
            supports_batch_execution=True,
            prefers_local_memory=True,
            transport_kind="pci_local",
            metadata={},
        ),
        transfer_plan=InferenceMemoryTransferPlan(
            provider_name="local_gpu_provider",
            tier=InferenceCapacityTier.LOCAL_GPU,
            transport_kind="pci_local",
            expected_overhead_ms=2,
            reason="test",
        ),
        health=InferenceProviderHealth(
            provider_name="local_gpu_provider",
            healthy=True,
            availability_score=0.99,
            latency_score=0.95,
            error_rate=0.0,
            saturation_score=0.72,
        ),
    )
    assert plan.pressure_band == "high"
    assert plan.locality_scope == "local"
    assert plan.expected_queue_penalty_ms >= 3

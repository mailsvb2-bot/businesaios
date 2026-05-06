from execution.inference_capacity_contract import InferenceCapacityTier
from execution.inference_capacity_policy import InferenceCapacityPolicyContext
from execution.inference_capacity_router import InferenceCapacityRouter
from execution.inference_dispatch_orchestrator import InferenceDispatchOrchestrator
from execution.inference_provider_contract import InferenceRequest
from runtime.inference.providers.local_gpu_provider import LocalGPUProvider


def test_inference_dispatch_records_pressure_and_locality_evidence():
    provider = LocalGPUProvider()
    router = InferenceCapacityRouter(providers={provider.name: provider})
    orchestrator = InferenceDispatchOrchestrator(
        providers={provider.name: provider},
        router=router,
    )
    record = orchestrator.dispatch(
        request=InferenceRequest(
            request_id="req-1",
            model="test",
            prompt="hello",
            max_output_tokens=32,
            metadata={"requested_batch_items": 8},
        ),
        preferred_tier=InferenceCapacityTier.LOCAL_GPU,
        policy_context=InferenceCapacityPolicyContext(tenant_id="tenant-a", distributed_network_enabled=False, premium_cloud_enabled=False, max_allowed_tier=InferenceCapacityTier.LOCAL_GPU),
    )
    assert record.evidence["acceleration_pressure_band"] in {"low", "moderate", "high", "critical"}
    assert record.evidence["acceleration_locality_scope"] in {"local", "nearby_remote", "distributed_remote", "external_remote"}
    assert "acceleration_saturation_score" in record.evidence

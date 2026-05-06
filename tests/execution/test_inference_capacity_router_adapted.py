from execution.inference_capacity_contract import InferenceCapacityTier
from execution.inference_capacity_policy import InferenceCapacityPolicyContext
from execution.inference_capacity_router import InferenceCapacityRouter
from execution.inference_workload_contract import InferenceWorkloadDescriptor, InferenceWorkloadKind
from runtime.inference.providers.cpu_fallback_provider import CPUFallbackProvider
from runtime.inference.providers.local_gpu_provider import LocalGPUProvider


def test_inference_capacity_router_prefers_local_gpu_when_available():
    router = InferenceCapacityRouter(
        providers={
            'cpu_fallback_provider': CPUFallbackProvider(),
            'local_gpu_provider': LocalGPUProvider(),
        }
    )
    selection = router.select(
        workload=InferenceWorkloadDescriptor(
            workload_id='w1',
            kind=InferenceWorkloadKind.CHAT,
            context_tokens=1024,
            expected_output_tokens=512,
        ),
        preferred_tier=InferenceCapacityTier.LOCAL_GPU,
        policy_context=InferenceCapacityPolicyContext(
            tenant_id='tenant-a',
            distributed_network_enabled=False,
            premium_cloud_enabled=True,
            max_allowed_tier=InferenceCapacityTier.LOCAL_GPU,
        ),
    )
    assert selection.provider_name == 'local_gpu_provider'
    assert selection.tier == InferenceCapacityTier.LOCAL_GPU

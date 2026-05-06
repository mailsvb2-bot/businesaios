from execution.inference_capacity_contract import InferenceCapacityTier
from execution.inference_capacity_policy import InferenceCapacityPolicyContext
from execution.inference_provider_contract import InferenceRequest
from execution.inference_dispatch_orchestrator import InferenceDispatchOrchestrator
from execution.inference_capacity_router import InferenceCapacityRouter
from runtime.inference.providers.cpu_fallback_provider import CPUFallbackProvider
from runtime.inference.providers.local_gpu_provider import LocalGPUProvider


class FailingLocalGPUProvider(LocalGPUProvider):
    def infer(self, request):
        raise RuntimeError('simulated local gpu failure')


def test_inference_dispatch_failsover_after_provider_failure():
    providers = {
        'cpu_fallback_provider': CPUFallbackProvider(),
        'local_gpu_provider': FailingLocalGPUProvider(),
    }
    router = InferenceCapacityRouter(providers=providers)
    orchestrator = InferenceDispatchOrchestrator(providers=providers, router=router)
    record = orchestrator.dispatch(
        request=InferenceRequest(
            request_id='r-failover',
            model='test-model',
            prompt='hello failover',
            max_output_tokens=64,
            metadata={'tenant_id': 'tenant-a', 'workload_id': 'w1'},
        ),
        preferred_tier=InferenceCapacityTier.LOCAL_GPU,
        policy_context=InferenceCapacityPolicyContext(
            tenant_id='tenant-a',
            distributed_network_enabled=False,
            premium_cloud_enabled=True,
            max_allowed_tier=InferenceCapacityTier.LOCAL_GPU,
        ),
    )
    assert record.selected_provider == 'cpu_fallback_provider'
    assert record.evidence['fallback_reason'] == 'provider_failure_failover'


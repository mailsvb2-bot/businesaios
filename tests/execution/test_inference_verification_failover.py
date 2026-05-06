from execution.inference_capacity_contract import InferenceCapacityTier
from execution.inference_capacity_policy import InferenceCapacityPolicyContext
from execution.inference_provider_contract import InferenceRequest
from execution.inference_dispatch_orchestrator import InferenceDispatchOrchestrator
from execution.inference_capacity_router import InferenceCapacityRouter
from runtime.inference.providers.cpu_fallback_provider import CPUFallbackProvider
from runtime.inference.providers.local_gpu_provider import LocalGPUProvider


class EmptyLocalGPUProvider(LocalGPUProvider):
    def infer(self, request):
        response = super().infer(request)
        return type(response)(
            request_id=response.request_id,
            provider_name=response.provider_name,
            tier=response.tier,
            output_text='',
            prompt_tokens=response.prompt_tokens,
            completion_tokens=0,
            latency_ms=response.latency_ms,
            estimated_cost_usd=response.estimated_cost_usd,
            raw_payload=response.raw_payload,
        )


def test_inference_dispatch_failsover_after_verification_reject():
    providers = {
        'cpu_fallback_provider': CPUFallbackProvider(),
        'local_gpu_provider': EmptyLocalGPUProvider(),
    }
    router = InferenceCapacityRouter(providers=providers)
    orchestrator = InferenceDispatchOrchestrator(providers=providers, router=router)
    record = orchestrator.dispatch(
        request=InferenceRequest(
            request_id='r-verify',
            model='test-model',
            prompt='hello verify',
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
    assert record.evidence['fallback_reason'] == 'verification_failover'
    assert record.verification.accepted is True

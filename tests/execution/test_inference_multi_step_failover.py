from execution.inference_capacity_contract import InferenceCapacityTier
from execution.inference_capacity_policy import InferenceCapacityPolicyContext
from execution.inference_capacity_router import InferenceCapacityRouter
from execution.inference_dispatch_orchestrator import InferenceDispatchOrchestrator
from execution.inference_provider_contract import InferenceRequest
from execution.inference_result_verifier import InferenceResultVerifier
from execution.inference_workload_classifier import InferenceWorkloadClassifier
from runtime.inference.providers.cpu_fallback_provider import CPUFallbackProvider
from runtime.inference.providers.dedicated_gpu_provider import DedicatedGPUProvider
from runtime.inference.providers.local_gpu_provider import LocalGPUProvider
from runtime.inference.providers.provider_circuit_breaker import ProviderCircuitBreaker
from runtime.inference.providers.provider_rate_limit_guard import ProviderRateLimitGuard
from runtime.inference.providers.provider_retry_adapter import ProviderRetryAdapter, RetryPolicy


class FailingLocalGPUProvider(LocalGPUProvider):
    def infer(self, request):
        raise RuntimeError('local gpu failure')


class RejectingDedicatedGPUProvider(DedicatedGPUProvider):
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


def test_dispatch_orchestrator_uses_multi_step_failover_chain():
    providers = {
        'cpu_fallback_provider': CPUFallbackProvider(),
        'local_gpu_provider': FailingLocalGPUProvider(),
        'dedicated_gpu_provider': RejectingDedicatedGPUProvider(),
    }
    router = InferenceCapacityRouter(providers=providers)
    orchestrator = InferenceDispatchOrchestrator(
        providers=providers,
        router=router,
        classifier=InferenceWorkloadClassifier(),
        verifier=InferenceResultVerifier(),
        retry_adapter=ProviderRetryAdapter(RetryPolicy(max_attempts=1)),
        circuit_breaker=ProviderCircuitBreaker(),
        rate_limit_guard=ProviderRateLimitGuard(max_requests_per_minute=10),
    )
    record = orchestrator.dispatch(
        request=InferenceRequest('r1', 'model', 'hello world', 32, metadata={'workload_id': 'w1'}),
        preferred_tier=InferenceCapacityTier.LOCAL_GPU,
        policy_context=InferenceCapacityPolicyContext(tenant_id='tenant-a', distributed_network_enabled=False, premium_cloud_enabled=False, max_allowed_tier=InferenceCapacityTier.PREMIUM_EXTERNAL_CLOUD),
    )
    assert record.selected_provider == 'cpu_fallback_provider'
    assert record.verification.accepted is True
    assert 'local_gpu_provider' in record.evidence['attempted_providers']
    assert 'dedicated_gpu_provider' in record.evidence['attempted_providers']
    assert record.evidence['recovery_attempt_count'] == '3'

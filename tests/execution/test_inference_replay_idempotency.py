from execution.inference_capacity_contract import InferenceCapacityTier
from execution.inference_capacity_policy import InferenceCapacityPolicyContext
from execution.inference_provider_contract import InferenceRequest
from boot.factories.inference_capacity_router_factory import build_inference_capacity_router
from boot.factories.inference_dispatch_orchestrator_factory import build_inference_dispatch_orchestrator
from boot.factories.inference_provider_factory import build_inference_provider_registry


def test_inference_dispatch_reuses_replay_safe_request_result():
    registry = build_inference_provider_registry()
    router = build_inference_capacity_router(registry=registry)
    orchestrator = build_inference_dispatch_orchestrator(registry=registry, router=router)
    request = InferenceRequest(
        request_id="replay-1",
        model="test-model",
        prompt="hello world",
        max_output_tokens=64,
        metadata={"workload_id": "w1", "tenant_id": "tenant-a", "replay_safe_dispatch": "true"},
    )
    ctx = InferenceCapacityPolicyContext(
        tenant_id='tenant-a',
        distributed_network_enabled=True,
        premium_cloud_enabled=True,
        max_allowed_tier=InferenceCapacityTier.PREMIUM_EXTERNAL_CLOUD,
    )
    first = orchestrator.dispatch(request=request, preferred_tier=InferenceCapacityTier.LOCAL_GPU, policy_context=ctx)
    second = orchestrator.dispatch(request=request, preferred_tier=InferenceCapacityTier.LOCAL_GPU, policy_context=ctx)
    assert first is second
    assert second.evidence['recovery_attempt_count'] == '1'

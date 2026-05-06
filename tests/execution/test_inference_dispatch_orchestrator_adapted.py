from execution.inference_capacity_contract import InferenceCapacityTier
from execution.inference_capacity_policy import InferenceCapacityPolicyContext
from execution.inference_provider_contract import InferenceRequest
from boot.factories.inference_capacity_router_factory import build_inference_capacity_router
from boot.factories.inference_dispatch_orchestrator_factory import build_inference_dispatch_orchestrator
from boot.factories.inference_provider_factory import build_inference_provider_registry


def test_inference_dispatch_orchestrator_returns_verified_record():
    registry = build_inference_provider_registry()
    router = build_inference_capacity_router(registry=registry)
    orchestrator = build_inference_dispatch_orchestrator(registry=registry, router=router)
    record = orchestrator.dispatch(
        request=InferenceRequest(
            request_id='r1',
            model='test-model',
            prompt='hello world',
            max_output_tokens=128,
            metadata={'workload_id': 'w1', 'tenant_id': 'tenant-a'},
        ),
        preferred_tier=InferenceCapacityTier.LOCAL_GPU,
        policy_context=InferenceCapacityPolicyContext(
            tenant_id='tenant-a',
            distributed_network_enabled=False,
            premium_cloud_enabled=True,
            max_allowed_tier=InferenceCapacityTier.PREMIUM_EXTERNAL_CLOUD,
        ),
    )
    assert record.selected_provider
    assert record.verification.accepted is True
    assert record.response.output_text



def test_inference_dispatch_orchestrator_applies_cold_start_guard():
    registry = build_inference_provider_registry()
    router = build_inference_capacity_router(registry=registry)
    orchestrator = build_inference_dispatch_orchestrator(registry=registry, router=router)
    record = orchestrator.dispatch(
        request=InferenceRequest(
            request_id='r2',
            model='test-model',
            prompt='hello world',
            max_output_tokens=128,
            metadata={'workload_id': 'w2', 'tenant_id': 'tenant-a', 'historical_inference_executions': 0},
        ),
        preferred_tier=InferenceCapacityTier.DISTRIBUTED_GPU_NETWORK,
        policy_context=InferenceCapacityPolicyContext(
            tenant_id='tenant-a',
            distributed_network_enabled=True,
            premium_cloud_enabled=True,
            max_allowed_tier=InferenceCapacityTier.PREMIUM_EXTERNAL_CLOUD,
        ),
    )
    assert record.selected_tier == InferenceCapacityTier.LOCAL_GPU.value
    assert record.evidence['cold_start_reason'] == 'cold_start_conservative_downgrade'


def test_inference_dispatch_orchestrator_applies_budget_degradation():
    registry = build_inference_provider_registry()
    router = build_inference_capacity_router(registry=registry)
    orchestrator = build_inference_dispatch_orchestrator(registry=registry, router=router)
    record = orchestrator.dispatch(
        request=InferenceRequest(
            request_id='r3',
            model='test-model',
            prompt='x' * 12000,
            max_output_tokens=128,
            metadata={
                'workload_id': 'w3',
                'tenant_id': 'tenant-a',
                'historical_inference_executions': 50,
                'inference_budget_cap_usd': 0.001,
            },
        ),
        preferred_tier=InferenceCapacityTier.PREMIUM_EXTERNAL_CLOUD,
        policy_context=InferenceCapacityPolicyContext(
            tenant_id='tenant-a',
            distributed_network_enabled=True,
            premium_cloud_enabled=True,
            max_allowed_tier=InferenceCapacityTier.PREMIUM_EXTERNAL_CLOUD,
        ),
    )
    assert record.selected_tier == InferenceCapacityTier.LOCAL_GPU.value
    assert record.evidence['degradation_mode'] == 'budget_guarded_degradation'
    assert float(record.evidence['fairness_allocated_share']) > 0.0

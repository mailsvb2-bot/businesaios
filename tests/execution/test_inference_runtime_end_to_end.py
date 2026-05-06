from execution.inference_capacity_contract import InferenceCapacityTier
from execution.inference_capacity_policy import InferenceCapacityPolicyContext
from execution.inference_provider_contract import InferenceRequest
from boot.factories.inference_capacity_router_factory import build_inference_capacity_router
from boot.factories.inference_dispatch_orchestrator_factory import build_inference_dispatch_orchestrator
from boot.factories.inference_provider_factory import build_inference_provider_registry


def test_inference_runtime_end_to_end_distributed_allowed_path_records_policy_fields():
    registry = build_inference_provider_registry()
    router = build_inference_capacity_router(registry=registry)
    orchestrator = build_inference_dispatch_orchestrator(registry=registry, router=router)
    record = orchestrator.dispatch(
        request=InferenceRequest(
            request_id='r-e2e',
            model='test-model',
            prompt='distributed inference request',
            max_output_tokens=128,
            metadata={
                'workload_id': 'w-e2e',
                'tenant_id': 'tenant-e2e',
                'historical_inference_executions': 50,
                'tenant_queue_depth': 5,
                'inference_expected_benefit_usd': 10.0,
            },
        ),
        preferred_tier=InferenceCapacityTier.DISTRIBUTED_GPU_NETWORK,
        policy_context=InferenceCapacityPolicyContext(
            tenant_id='tenant-e2e',
            distributed_network_enabled=True,
            premium_cloud_enabled=True,
            max_allowed_tier=InferenceCapacityTier.DISTRIBUTED_GPU_NETWORK,
        ),
    )
    assert record.selected_provider == 'distributed_gpu_provider'
    assert record.verification.accepted is True
    assert record.evidence['policy_reason'] == 'allowed'
    assert record.evidence['degradation_mode'] == 'steady_state'

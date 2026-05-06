from execution.inference_capacity_contract import InferenceCapacityTier
from execution.inference_capacity_policy import InferenceCapacityPolicyContext
from execution.inference_provider_contract import InferenceRequest
from observability.inference_acceleration_log import InferenceAccelerationLog
from boot.factories.inference_capacity_router_factory import build_inference_capacity_router
from boot.factories.inference_provider_factory import build_inference_provider_registry
from execution.inference_dispatch_orchestrator import InferenceDispatchOrchestrator


def test_inference_dispatch_orchestrator_records_acceleration_log_event():
    registry = build_inference_provider_registry()
    router = build_inference_capacity_router(registry=registry)
    acceleration_log = InferenceAccelerationLog()
    orchestrator = InferenceDispatchOrchestrator(
        providers=registry.as_dict(),
        router=router,
        acceleration_log=acceleration_log,
    )
    record = orchestrator.dispatch(
        request=InferenceRequest(
            request_id='r-log',
            model='test-model',
            prompt='accelerated local gpu prompt',
            max_output_tokens=64,
            metadata={
                'tenant_id': 'tenant-log',
                'historical_inference_executions': 10,
                'requested_batch_items': 3,
            },
        ),
        preferred_tier=InferenceCapacityTier.LOCAL_GPU,
        policy_context=InferenceCapacityPolicyContext(
            tenant_id='tenant-log',
            distributed_network_enabled=True,
            premium_cloud_enabled=True,
            max_allowed_tier=InferenceCapacityTier.LOCAL_GPU,
        ),
    )
    events = acceleration_log.list_events()
    assert len(events) == 1
    assert events[0].tenant_id == 'tenant-log'
    assert events[0].provider_name == record.selected_provider
    assert events[0].tier == record.selected_tier

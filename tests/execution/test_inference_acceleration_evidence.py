from boot.factories.inference_provider_factory import build_inference_provider_registry
from execution.inference_capacity_contract import InferenceCapacityTier
from execution.inference_capacity_policy import InferenceCapacityPolicyContext
from execution.inference_capacity_router import InferenceCapacityRouter
from execution.inference_dispatch_orchestrator import InferenceDispatchOrchestrator
from execution.inference_provider_contract import InferenceRequest


def test_inference_dispatch_orchestrator_records_acceleration_evidence():
    registry = build_inference_provider_registry()
    providers = registry.as_dict()
    router = InferenceCapacityRouter(providers=providers)
    orchestrator = InferenceDispatchOrchestrator(providers=providers, router=router)

    record = orchestrator.dispatch(
        request=InferenceRequest(
            request_id='req-accel',
            model='gpt-test',
            prompt='hello local gpu',
            max_output_tokens=64,
            metadata={'requested_batch_items': 7},
        ),
        preferred_tier=InferenceCapacityTier.LOCAL_GPU,
        policy_context=InferenceCapacityPolicyContext(
            tenant_id='tenant-a',
            distributed_network_enabled=True,
            premium_cloud_enabled=True,
            max_allowed_tier=InferenceCapacityTier.LOCAL_GPU,
        ),
    )

    assert record.selected_provider == 'local_gpu_provider'
    assert record.evidence['acceleration_execution_mode'] == 'accelerated'
    assert record.evidence['acceleration_device_class'] == 'local_gpu'
    assert record.evidence['acceleration_transport_kind'] == 'pci_local'
    assert record.evidence['acceleration_batch_items'] == '7'

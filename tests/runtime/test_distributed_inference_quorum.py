from execution.inference_provider_contract import InferenceRequest
from runtime.inference.providers.distributed_gpu_provider import DistributedGPUProvider


def test_distributed_provider_supports_consensus_mode():
    provider = DistributedGPUProvider()
    response = provider.infer(InferenceRequest(
        request_id='q1',
        model='test-model',
        prompt='hello world again',
        max_output_tokens=64,
        metadata={'distributed_consensus_required': 'true'},
    ))
    assert response.provider_name == 'distributed_gpu_provider'
    assert response.raw_payload['node_id']

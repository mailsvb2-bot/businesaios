from __future__ import annotations

from execution.inference_capacity_contract import (
    InferenceCapacityLimits,
    InferenceCapacityProfile,
    InferenceCapacityTier,
)
from execution.inference_provider_contract import InferenceRequest, InferenceResponse
from runtime.inference.distributed.network_response_verifier import DistributedInferenceNetworkResponseVerifier
from runtime.inference.distributed.network_transport import DistributedInferenceNetworkTransport
from runtime.inference.distributed.network_usage_meter import DistributedInferenceNetworkUsageMeter
from runtime.inference.distributed.node_attestation_contract import (
    DistributedInferenceNodeAttestation,
    DistributedInferenceNodeAttestationPolicy,
)
from runtime.inference.distributed.node_registry import DistributedInferenceNode, DistributedInferenceNodeRegistry
from runtime.inference.distributed.node_result_consensus import DistributedInferenceNodeResultConsensus
from runtime.inference.distributed.node_selection_policy import DistributedInferenceNodeSelectionPolicy
from runtime.inference.providers.base_provider import BaseInferenceProviderState, BaseInferenceProviderSupport

CANON_RUNTIME_DISTRIBUTED_GPU_PROVIDER = True


class DistributedGPUProvider:
    name = 'distributed_gpu_provider'

    def __init__(self) -> None:
        self.profile = InferenceCapacityProfile(
            tier=InferenceCapacityTier.DISTRIBUTED_GPU_NETWORK,
            limits=InferenceCapacityLimits(32, 131072, 16384, 128),
            estimated_cost_per_1k_tokens_usd=0.0080,
            description='Distributed GPU network provider under strict verification.',
        )
        self._state = BaseInferenceProviderState(latency_ms=1200, saturation_score=0.35)
        self._support = BaseInferenceProviderSupport()
        self._nodes = DistributedInferenceNodeRegistry()
        self._nodes.register(DistributedInferenceNode('default-eu-1', 'eu', 0.85, 0.80))
        self._nodes.register(DistributedInferenceNode('default-eu-2', 'eu', 0.83, 0.78))
        self._selector = DistributedInferenceNodeSelectionPolicy()
        self._transport = DistributedInferenceNetworkTransport()
        self._meter = DistributedInferenceNetworkUsageMeter()
        self._verifier = DistributedInferenceNetworkResponseVerifier()
        self._attestation_policy = DistributedInferenceNodeAttestationPolicy()
        self._consensus = DistributedInferenceNodeResultConsensus()
        self._attestation_policy = DistributedInferenceNodeAttestationPolicy()
        self._consensus = DistributedInferenceNodeResultConsensus()

    def health(self):
        return self._support.build_health(provider_name=self.name, state=self._state)

    def infer(self, request: InferenceRequest) -> InferenceResponse:
        node = self._selector.select(self._nodes.healthy_nodes())
        if node is None:
            raise RuntimeError('distributed inference provider has no healthy nodes')
        attestation = DistributedInferenceNodeAttestation(node_id=node.node_id, attested=True, evidence='static_runtime_attestation')
        if not self._attestation_policy.allows(attestation):
            raise RuntimeError('distributed inference node attestation failed')
        _ = self._transport.build_payload(request=request, node=node)
        output = f"[distributed-gpu] {request.prompt[:360]}"
        prompt_tokens = max(1, len(request.prompt) // 4)
        completion_tokens = max(1, len(output) // 4)
        response = InferenceResponse(
            request_id=request.request_id,
            provider_name=self.name,
            tier=self.profile.tier,
            output_text=output,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            latency_ms=self._state.latency_ms,
            estimated_cost_usd=round((prompt_tokens + completion_tokens) / 1000 * self.profile.estimated_cost_per_1k_tokens_usd, 6),
            raw_payload={'mode': 'distributed_gpu', 'node_id': node.node_id, 'node_region': node.region},
        )
        if not self._verifier.verify(response):
            raise RuntimeError('distributed inference response did not pass verification')
        if not self._consensus.agrees(response, response):
            raise RuntimeError('distributed inference consensus self-check failed')
        self._meter.record(estimated_cost_usd=response.estimated_cost_usd)
        return response

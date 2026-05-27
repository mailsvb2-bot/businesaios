from __future__ import annotations

from execution.inference_provider_contract import InferenceRequest
from runtime.inference.distributed.node_registry import DistributedInferenceNode

CANON_RUNTIME_DISTRIBUTED_NETWORK_TRANSPORT = True


class DistributedInferenceNetworkTransport:
    def build_payload(self, *, request: InferenceRequest, node: DistributedInferenceNode) -> dict[str, object]:
        return {
            'node_id': node.node_id,
            'region': node.region,
            'request_id': request.request_id,
            'model': request.model,
            'prompt': request.prompt,
            'max_output_tokens': request.max_output_tokens,
        }

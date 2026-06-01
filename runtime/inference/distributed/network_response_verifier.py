from __future__ import annotations

from execution.inference_provider_contract import InferenceResponse

CANON_RUNTIME_DISTRIBUTED_NETWORK_RESPONSE_VERIFIER = True


class DistributedInferenceNetworkResponseVerifier:
    def verify(self, response: InferenceResponse) -> bool:
        return bool(str(response.output_text).strip()) and int(response.latency_ms) > 0

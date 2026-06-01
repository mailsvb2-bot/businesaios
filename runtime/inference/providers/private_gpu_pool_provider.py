from __future__ import annotations

from execution.inference_capacity_contract import (
    InferenceCapacityLimits,
    InferenceCapacityProfile,
    InferenceCapacityTier,
)
from execution.inference_provider_contract import InferenceRequest, InferenceResponse
from runtime.inference.providers.base_provider import BaseInferenceProviderState, BaseInferenceProviderSupport

CANON_RUNTIME_PRIVATE_GPU_POOL_PROVIDER = True


class PrivateGPUPoolProvider:
    name = 'private_gpu_pool_provider'

    def __init__(self) -> None:
        self.profile = InferenceCapacityProfile(
            tier=InferenceCapacityTier.PRIVATE_GPU_POOL,
            limits=InferenceCapacityLimits(16, 131072, 16384, 64),
            estimated_cost_per_1k_tokens_usd=0.0130,
            description='Private GPU pool for multi-business autonomous workloads.',
        )
        self._state = BaseInferenceProviderState(latency_ms=500, saturation_score=0.22)
        self._support = BaseInferenceProviderSupport()

    def health(self):
        return self._support.build_health(provider_name=self.name, state=self._state)

    def infer(self, request: InferenceRequest) -> InferenceResponse:
        output = f"[private-pool] {request.prompt[:420]}"
        prompt_tokens = max(1, len(request.prompt) // 4)
        completion_tokens = max(1, len(output) // 4)
        return InferenceResponse(
            request_id=request.request_id,
            provider_name=self.name,
            tier=self.profile.tier,
            output_text=output,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            latency_ms=self._state.latency_ms,
            estimated_cost_usd=round((prompt_tokens + completion_tokens) / 1000 * self.profile.estimated_cost_per_1k_tokens_usd, 6),
            raw_payload={'mode': 'private_gpu_pool'},
        )

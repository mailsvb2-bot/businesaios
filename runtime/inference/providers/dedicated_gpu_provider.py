from __future__ import annotations

from execution.inference_capacity_contract import InferenceCapacityLimits, InferenceCapacityProfile, InferenceCapacityTier
from execution.inference_provider_contract import InferenceRequest, InferenceResponse
from runtime.inference.providers.base_provider import BaseInferenceProviderState, BaseInferenceProviderSupport


CANON_RUNTIME_DEDICATED_GPU_PROVIDER = True


class DedicatedGPUProvider:
    name = 'dedicated_gpu_provider'

    def __init__(self) -> None:
        self.profile = InferenceCapacityProfile(
            tier=InferenceCapacityTier.DEDICATED_GPU,
            limits=InferenceCapacityLimits(8, 65536, 8192, 32),
            estimated_cost_per_1k_tokens_usd=0.0100,
            description='Reserved dedicated GPU tier for stable production inference.',
        )
        self._state = BaseInferenceProviderState(latency_ms=650, saturation_score=0.25)
        self._support = BaseInferenceProviderSupport()

    def health(self):
        return self._support.build_health(provider_name=self.name, state=self._state)

    def infer(self, request: InferenceRequest) -> InferenceResponse:
        output = f"[dedicated-gpu] {request.prompt[:300]}"
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
            raw_payload={'mode': 'dedicated_gpu'},
        )

from __future__ import annotations

from dataclasses import dataclass

from execution.inference_provider_contract import InferenceProviderHealth


CANON_RUNTIME_INFERENCE_BASE_PROVIDER = True


@dataclass
class BaseInferenceProviderState:
    latency_ms: int = 500
    error_rate: float = 0.01
    saturation_score: float = 0.10
    healthy: bool = True


class BaseInferenceProviderSupport:
    def build_health(self, *, provider_name: str, state: BaseInferenceProviderState) -> InferenceProviderHealth:
        provider_state = state
        is_healthy = bool(provider_state.healthy)
        return InferenceProviderHealth(
            provider_name=provider_name,
            healthy=is_healthy,
            availability_score=1.0 if is_healthy else 0.0,
            latency_score=max(0.0, 1.0 - min(float(provider_state.latency_ms) / 10000.0, 1.0)),
            error_rate=max(0.0, min(1.0, float(provider_state.error_rate))),
            saturation_score=max(0.0, min(1.0, float(provider_state.saturation_score))),
            notes='Synthetic deterministic provider health snapshot.',
        )

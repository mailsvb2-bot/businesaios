from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Protocol

from execution.inference_capacity_contract import InferenceCapacityProfile, InferenceCapacityTier


CANON_INFERENCE_PROVIDER_CONTRACT = True


@dataclass(frozen=True)
class InferenceRequest:
    request_id: str
    model: str
    prompt: str
    max_output_tokens: int
    temperature: float = 0.0
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class InferenceResponse:
    request_id: str
    provider_name: str
    tier: InferenceCapacityTier
    output_text: str
    prompt_tokens: int
    completion_tokens: int
    latency_ms: int
    estimated_cost_usd: float
    raw_payload: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class InferenceProviderHealth:
    provider_name: str
    healthy: bool
    availability_score: float
    latency_score: float
    error_rate: float
    saturation_score: float
    notes: str = ''


class InferenceProvider(Protocol):
    name: str
    profile: InferenceCapacityProfile

    def health(self) -> InferenceProviderHealth:
        ...

    def infer(self, request: InferenceRequest) -> InferenceResponse:
        ...

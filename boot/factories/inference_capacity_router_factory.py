from __future__ import annotations

from execution.inference_capacity_router import InferenceCapacityRouter
from runtime.inference.providers.provider_registry import InferenceProviderRegistry


def build_inference_capacity_router(*, registry: InferenceProviderRegistry) -> InferenceCapacityRouter:
    return InferenceCapacityRouter(providers=registry.as_dict())


__all__ = ['build_inference_capacity_router']

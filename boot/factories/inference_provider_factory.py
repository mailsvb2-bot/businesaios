from __future__ import annotations

from runtime.inference.providers.cpu_fallback_provider import CPUFallbackProvider
from runtime.inference.providers.dedicated_gpu_provider import DedicatedGPUProvider
from runtime.inference.providers.distributed_gpu_provider import DistributedGPUProvider
from runtime.inference.providers.external_cloud_inference_provider import ExternalCloudInferenceProvider
from runtime.inference.providers.local_gpu_provider import LocalGPUProvider
from runtime.inference.providers.private_gpu_pool_provider import PrivateGPUPoolProvider
from runtime.inference.providers.provider_registry import InferenceProviderRegistry


def build_inference_provider_registry() -> InferenceProviderRegistry:
    return InferenceProviderRegistry(
        [
            CPUFallbackProvider(),
            LocalGPUProvider(),
            DedicatedGPUProvider(),
            PrivateGPUPoolProvider(),
            DistributedGPUProvider(),
            ExternalCloudInferenceProvider(),
        ]
    )


__all__ = ['build_inference_provider_registry']

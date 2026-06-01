from __future__ import annotations

"""Inference providers live under the runtime execution boundary only.

The package root is the owner surface for runtime inference provider exports.
"""

from runtime.inference.providers.cpu_fallback_provider import CPUFallbackProvider
from runtime.inference.providers.dedicated_gpu_provider import DedicatedGPUProvider
from runtime.inference.providers.distributed_gpu_provider import DistributedGPUProvider
from runtime.inference.providers.external_cloud_inference_provider import ExternalCloudInferenceProvider
from runtime.inference.providers.local_gpu_provider import LocalGPUProvider
from runtime.inference.providers.private_gpu_pool_provider import PrivateGPUPoolProvider
from runtime.inference.providers.provider_acceleration_pressure_policy import (
    InferenceAccelerationPressurePlan,
    ProviderAccelerationPressurePolicy,
)
from runtime.inference.providers.provider_acceleration_profile import InferenceProviderAccelerationProfileCatalog
from runtime.inference.providers.provider_batch_execution_policy import ProviderBatchExecutionPolicy
from runtime.inference.providers.provider_circuit_breaker import ProviderCircuitBreaker
from runtime.inference.providers.provider_health_monitor import InferenceProviderHealthMonitor
from runtime.inference.providers.provider_memory_transfer_policy import ProviderMemoryTransferPolicy
from runtime.inference.providers.provider_rate_limit_guard import ProviderRateLimitGuard
from runtime.inference.providers.provider_registry import InferenceProviderRegistry
from runtime.inference.providers.provider_retry_adapter import ProviderRetryAdapter, RetryPolicy

CANON_RUNTIME_INFERENCE_PROVIDER_NAMESPACE = True
CANON_RUNTIME_INFERENCE_PROVIDER_PACKAGE_OWNER = True

__all__ = [
    'CANON_RUNTIME_INFERENCE_PROVIDER_NAMESPACE',
    'CANON_RUNTIME_INFERENCE_PROVIDER_PACKAGE_OWNER',
    'CPUFallbackProvider',
    'DedicatedGPUProvider',
    'DistributedGPUProvider',
    'ExternalCloudInferenceProvider',
    'InferenceProviderHealthMonitor',
    'InferenceProviderRegistry',
    'LocalGPUProvider',
    'PrivateGPUPoolProvider',
    'InferenceProviderAccelerationProfileCatalog',
    'ProviderBatchExecutionPolicy',
    'ProviderMemoryTransferPolicy',
    'ProviderAccelerationPressurePolicy',
    'InferenceAccelerationPressurePlan',
    'ProviderCircuitBreaker',
    'ProviderRateLimitGuard',
    'ProviderRetryAdapter',
    'RetryPolicy',
]

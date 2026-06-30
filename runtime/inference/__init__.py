"""Canonical runtime namespace for inference capacity execution.

This namespace does not introduce a second brain.
It contains only execution/runtime support for deterministic inference routing.
"""

from __future__ import annotations

from runtime.inference.distributed import (
    DistributedInferenceNetworkResponseVerifier,
    DistributedInferenceNetworkTransport,
    DistributedInferenceNetworkUsageMeter,
    DistributedInferenceNode,
    DistributedInferenceNodeAttestation,
    DistributedInferenceNodeAttestationPolicy,
    DistributedInferenceNodeHealthScoring,
    DistributedInferenceNodeRegistry,
    DistributedInferenceNodeResultConsensus,
    DistributedInferenceNodeSelectionPolicy,
    DistributedNetworkUsage,
)
from runtime.inference.providers import (
    CPUFallbackProvider,
    DedicatedGPUProvider,
    DistributedGPUProvider,
    ExternalCloudInferenceProvider,
    InferenceProviderHealthMonitor,
    InferenceProviderRegistry,
    LocalGPUProvider,
    PrivateGPUPoolProvider,
    ProviderCircuitBreaker,
    ProviderRateLimitGuard,
    ProviderRetryAdapter,
    RetryPolicy,
)
from runtime.inference.provisioning import (
    InferenceCapacityManager,
    InferenceCapacityState,
    InferenceCapacityStateStore,
    InferenceCapacityTransitionJournal,
    InferenceCapacityTransitionRecord,
    InferenceUpgradeCooldownTracker,
)

CANON_RUNTIME_INFERENCE_NAMESPACE = True
CANON_RUNTIME_INFERENCE_PACKAGE_OWNER = True
__all__ = [
    'CANON_RUNTIME_INFERENCE_NAMESPACE',
    'CANON_RUNTIME_INFERENCE_PACKAGE_OWNER',
    'CPUFallbackProvider',
    'DedicatedGPUProvider',
    'DistributedGPUProvider',
    'DistributedInferenceNetworkResponseVerifier',
    'DistributedInferenceNetworkTransport',
    'DistributedInferenceNetworkUsageMeter',
    'DistributedInferenceNode',
    'DistributedInferenceNodeAttestation',
    'DistributedInferenceNodeAttestationPolicy',
    'DistributedInferenceNodeHealthScoring',
    'DistributedInferenceNodeRegistry',
    'DistributedInferenceNodeResultConsensus',
    'DistributedInferenceNodeSelectionPolicy',
    'DistributedNetworkUsage',
    'ExternalCloudInferenceProvider',
    'InferenceCapacityManager',
    'InferenceCapacityState',
    'InferenceCapacityStateStore',
    'InferenceCapacityTransitionJournal',
    'InferenceCapacityTransitionRecord',
    'InferenceProviderHealthMonitor',
    'InferenceProviderRegistry',
    'InferenceUpgradeCooldownTracker',
    'LocalGPUProvider',
    'PrivateGPUPoolProvider',
    'ProviderCircuitBreaker',
    'ProviderRateLimitGuard',
    'ProviderRetryAdapter',
    'RetryPolicy',
]


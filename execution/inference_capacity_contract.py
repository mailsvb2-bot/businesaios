from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Mapping


CANON_INFERENCE_CAPACITY_CONTRACT = True


class InferenceCapacityTier(str, Enum):
    CPU_FALLBACK = 'cpu_fallback'
    LOCAL_GPU = 'local_gpu'
    DEDICATED_GPU = 'dedicated_gpu'
    PRIVATE_GPU_POOL = 'private_gpu_pool'
    DISTRIBUTED_GPU_NETWORK = 'distributed_gpu_network'
    PREMIUM_EXTERNAL_CLOUD = 'premium_external_cloud'


@dataclass(frozen=True)
class InferenceCapacityLimits:
    max_parallel_jobs: int
    max_context_tokens: int
    max_output_tokens: int
    max_batch_items: int


@dataclass(frozen=True)
class InferenceCapacityProfile:
    tier: InferenceCapacityTier
    limits: InferenceCapacityLimits
    estimated_cost_per_1k_tokens_usd: float
    supports_multimodal: bool = False
    supports_strict_verification: bool = True
    description: str = ''


@dataclass(frozen=True)
class InferenceCapacityRequirement:
    required_context_tokens: int
    required_output_tokens: int
    required_parallelism: int = 1
    required_batch_items: int = 1
    multimodal: bool = False
    latency_sensitive: bool = False


@dataclass(frozen=True)
class InferenceCapacitySelection:
    tier: InferenceCapacityTier
    provider_name: str
    reason: str
    estimated_cost_usd: float
    metadata: Mapping[str, Any] = field(default_factory=dict)

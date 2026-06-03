from __future__ import annotations

from dataclasses import dataclass
from collections.abc import Mapping

from execution.inference_capacity_contract import InferenceCapacityTier


CANON_INFERENCE_ACCELERATION_CONTRACT = True


@dataclass(frozen=True)
class InferenceAccelerationProfile:
    tier: InferenceCapacityTier
    execution_mode: str
    device_class: str
    supports_batch_execution: bool
    prefers_local_memory: bool
    transport_kind: str
    metadata: Mapping[str, str]


@dataclass(frozen=True)
class InferenceBatchPlan:
    provider_name: str
    tier: InferenceCapacityTier
    batch_items: int
    reason: str


@dataclass(frozen=True)
class InferenceMemoryTransferPlan:
    provider_name: str
    tier: InferenceCapacityTier
    transport_kind: str
    expected_overhead_ms: int
    reason: str


@dataclass(frozen=True)
class InferenceAccelerationPressurePlan:
    pressure_band: str
    locality_scope: str
    saturation_score: float
    expected_queue_penalty_ms: int
    reason: str

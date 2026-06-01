from __future__ import annotations

from dataclasses import dataclass

from execution.inference_acceleration_contract import InferenceAccelerationProfile, InferenceMemoryTransferPlan
from execution.inference_provider_contract import InferenceProviderHealth

CANON_RUNTIME_INFERENCE_PROVIDER_ACCELERATION_PRESSURE_POLICY = True


@dataclass(frozen=True)
class InferenceAccelerationPressurePlan:
    pressure_band: str
    locality_scope: str
    saturation_score: float
    expected_queue_penalty_ms: int
    reason: str


class ProviderAccelerationPressurePolicy:
    """Canonical owner of acceleration pressure/locality facts for a selected provider.

    This does not choose providers. It only normalizes already-selected provider/runtime
    execution facts into a stable observability/evidence surface.
    """

    def plan(
        self,
        *,
        profile: InferenceAccelerationProfile,
        transfer_plan: InferenceMemoryTransferPlan,
        health: InferenceProviderHealth,
    ) -> InferenceAccelerationPressurePlan:
        saturation = max(0.0, min(1.0, float(health.saturation_score)))
        if saturation >= 0.85:
            pressure_band = 'critical'
        elif saturation >= 0.60:
            pressure_band = 'high'
        elif saturation >= 0.30:
            pressure_band = 'moderate'
        else:
            pressure_band = 'low'

        if profile.prefers_local_memory and profile.transport_kind in {'in_process', 'pci_local'}:
            locality_scope = 'local'
        elif profile.transport_kind in {'dedicated_fabric', 'private_network'}:
            locality_scope = 'nearby_remote'
        elif profile.transport_kind == 'distributed_network':
            locality_scope = 'distributed_remote'
        else:
            locality_scope = 'external_remote'

        queue_penalty = int(round(transfer_plan.expected_overhead_ms * (1.0 + saturation)))

        return InferenceAccelerationPressurePlan(
            pressure_band=pressure_band,
            locality_scope=locality_scope,
            saturation_score=round(saturation, 6),
            expected_queue_penalty_ms=max(queue_penalty, 0),
            reason='pressure/locality normalized from provider health and transport metadata',
        )

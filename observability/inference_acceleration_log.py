from __future__ import annotations

from dataclasses import dataclass
from time import time


CANON_OBSERVABILITY_INFERENCE_ACCELERATION_LOG = True


@dataclass(frozen=True)
class InferenceAccelerationEvent:
    ts: float
    tenant_id: str
    provider_name: str
    tier: str
    execution_mode: str
    device_class: str = 'unknown'
    transport_kind: str = 'unknown'
    prefers_local_memory: bool = False
    batch_items: int = 1
    provider_max_batch_items: int = 1
    expected_transfer_overhead_ms: int = 0
    saturation_score: float = 0.0
    pressure_band: str = 'unknown'
    locality_scope: str = 'unknown'
    expected_queue_penalty_ms: int = 0


class InferenceAccelerationLog:
    def __init__(self) -> None:
        self._events: list[InferenceAccelerationEvent] = []

    def record(
        self,
        *,
        tenant_id: str,
        provider_name: str,
        tier: str,
        execution_mode: str,
        device_class: str = 'unknown',
        transport_kind: str = 'unknown',
        prefers_local_memory: bool = False,
        batch_items: int = 1,
        provider_max_batch_items: int = 1,
        expected_transfer_overhead_ms: int = 0,
        saturation_score: float = 0.0,
        pressure_band: str = 'unknown',
        locality_scope: str = 'unknown',
        expected_queue_penalty_ms: int = 0,
    ) -> None:
        self._events.append(
            InferenceAccelerationEvent(
                ts=time(),
                tenant_id=str(tenant_id),
                provider_name=str(provider_name),
                tier=str(tier),
                execution_mode=str(execution_mode),
                device_class=str(device_class),
                transport_kind=str(transport_kind),
                prefers_local_memory=bool(prefers_local_memory),
                batch_items=max(int(batch_items), 1),
                provider_max_batch_items=max(int(provider_max_batch_items), 1),
                expected_transfer_overhead_ms=max(int(expected_transfer_overhead_ms), 0),
                saturation_score=max(0.0, min(float(saturation_score), 1.0)),
                pressure_band=str(pressure_band),
                locality_scope=str(locality_scope),
                expected_queue_penalty_ms=max(int(expected_queue_penalty_ms), 0),
            )
        )

    def list_events(self) -> tuple[InferenceAccelerationEvent, ...]:
        return tuple(self._events)

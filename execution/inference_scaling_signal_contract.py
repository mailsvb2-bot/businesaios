from __future__ import annotations

from dataclasses import dataclass


CANON_INFERENCE_SCALING_SIGNAL_CONTRACT = True


@dataclass(frozen=True)
class InferenceScalingSignalSnapshot:
    queue_depth: int
    backlog_age_seconds: int
    p95_latency_ms: int
    timeout_rate: float
    retry_rate: float
    budget_headroom_usd: float
    spend_burn_rate_usd_per_hour: float
    provider_health_floor: float
    utilization_ratio: float
    acceleration_saturation_score: float = 0.0
    acceleration_expected_queue_penalty_ms: int = 0
    acceleration_locality_scope: str = 'unknown'

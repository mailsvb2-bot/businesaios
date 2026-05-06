from __future__ import annotations

from execution.inference_scaling_signal_contract import InferenceScalingSignalSnapshot


CANON_INFERENCE_SCALING_SIGNAL_AGGREGATOR = True


class InferenceScalingSignalAggregator:
    def build_snapshot(
        self,
        *,
        queue_depth: int,
        backlog_age_seconds: int,
        p95_latency_ms: int,
        timeout_rate: float,
        retry_rate: float,
        budget_headroom_usd: float,
        spend_burn_rate_usd_per_hour: float,
        provider_health_floor: float,
        utilization_ratio: float,
        acceleration_saturation_score: float = 0.0,
        acceleration_expected_queue_penalty_ms: int = 0,
        acceleration_locality_scope: str = 'unknown',
    ) -> InferenceScalingSignalSnapshot:
        return InferenceScalingSignalSnapshot(
            queue_depth=max(0, int(queue_depth)),
            backlog_age_seconds=max(0, int(backlog_age_seconds)),
            p95_latency_ms=max(0, int(p95_latency_ms)),
            timeout_rate=max(0.0, float(timeout_rate)),
            retry_rate=max(0.0, float(retry_rate)),
            budget_headroom_usd=float(budget_headroom_usd),
            spend_burn_rate_usd_per_hour=max(0.0, float(spend_burn_rate_usd_per_hour)),
            provider_health_floor=max(0.0, min(1.0, float(provider_health_floor))),
            utilization_ratio=max(0.0, min(1.0, float(utilization_ratio))),
            acceleration_saturation_score=max(0.0, min(1.0, float(acceleration_saturation_score))),
            acceleration_expected_queue_penalty_ms=max(0, int(acceleration_expected_queue_penalty_ms)),
            acceleration_locality_scope=str(acceleration_locality_scope or 'unknown'),
        )

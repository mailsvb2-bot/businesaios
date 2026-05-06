from __future__ import annotations

from execution.inference_capacity_contract import InferenceCapacityTier
from execution.inference_escalation_decision_contract import InferenceEscalationAction
from execution.inference_escalation_engine import InferenceEscalationEngine
from execution.inference_scaling_signal_aggregator import InferenceScalingSignalAggregator


def _base_snapshot(**overrides):
    payload = dict(
        queue_depth=1,
        backlog_age_seconds=1,
        p95_latency_ms=50,
        timeout_rate=0.0,
        retry_rate=0.0,
        budget_headroom_usd=100.0,
        spend_burn_rate_usd_per_hour=1.0,
        provider_health_floor=0.9,
        utilization_ratio=0.2,
        acceleration_saturation_score=0.0,
        acceleration_expected_queue_penalty_ms=0,
        acceleration_locality_scope='local',
    )
    payload.update(overrides)
    return InferenceScalingSignalAggregator().build_snapshot(**payload)


def test_acceleration_pressure_can_trigger_escalation() -> None:
    engine = InferenceEscalationEngine()
    decision = engine.decide(
        current_tier=InferenceCapacityTier.CPU_FALLBACK,
        signals=_base_snapshot(acceleration_saturation_score=0.95, acceleration_expected_queue_penalty_ms=40),
    )
    assert decision.action == InferenceEscalationAction.ESCALATE
    assert decision.target_tier != InferenceCapacityTier.CPU_FALLBACK


def test_acceleration_pressure_blocks_deescalation() -> None:
    engine = InferenceEscalationEngine()
    decision = engine.decide(
        current_tier=InferenceCapacityTier.LOCAL_GPU,
        signals=_base_snapshot(
            utilization_ratio=0.0,
            timeout_rate=0.0,
            p95_latency_ms=1,
            acceleration_saturation_score=0.7,
            acceleration_expected_queue_penalty_ms=20,
            acceleration_locality_scope='distributed_remote',
        ),
    )
    assert decision.action == InferenceEscalationAction.STAY

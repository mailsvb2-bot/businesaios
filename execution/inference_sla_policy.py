from __future__ import annotations

from dataclasses import dataclass

from execution.inference_scaling_signal_contract import InferenceScalingSignalSnapshot


CANON_INFERENCE_SLA_POLICY = True


@dataclass(frozen=True)
class InferenceSLAPolicy:
    queue_high_threshold: int = 100
    backlog_age_high_seconds: int = 180
    p95_latency_high_ms: int = 9000
    utilization_high: float = 0.85
    queue_low_threshold: int = 20
    backlog_age_low_seconds: int = 30
    utilization_low: float = 0.35

    def wants_escalation(self, signals: InferenceScalingSignalSnapshot) -> bool:
        return (
            signals.queue_depth > self.queue_high_threshold
            or signals.backlog_age_seconds > self.backlog_age_high_seconds
            or signals.p95_latency_ms > self.p95_latency_high_ms
            or signals.utilization_ratio > self.utilization_high
        )

    def wants_deescalation(self, signals: InferenceScalingSignalSnapshot) -> bool:
        return (
            signals.queue_depth < self.queue_low_threshold
            and signals.backlog_age_seconds < self.backlog_age_low_seconds
            and signals.utilization_ratio < self.utilization_low
        )

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class MessagingPolicyAlertThresholds:
    high_all_failed_rate: float = 0.25
    high_blocked_trace_rate: float = 0.15
    low_success_rate: float = 0.60
    channel_concentration_rate: float = 0.80
    high_fallback_usage_rate: float = 0.40
    high_attempts_per_trace: float = 2.50
    no_activity_traces_total: float = 0.0

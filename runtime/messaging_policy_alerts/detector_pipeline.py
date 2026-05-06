from __future__ import annotations

from runtime.messaging_policy_alerts.detectors.channel_concentration import detect_channel_concentration
from runtime.messaging_policy_alerts.detectors.high_all_failed_rate import detect_high_all_failed_rate
from runtime.messaging_policy_alerts.detectors.high_attempts_per_trace import detect_high_attempts_per_trace
from runtime.messaging_policy_alerts.detectors.high_blocked_trace_rate import detect_high_blocked_trace_rate
from runtime.messaging_policy_alerts.detectors.high_fallback_usage import detect_high_fallback_usage
from runtime.messaging_policy_alerts.detectors.low_success_rate import detect_low_success_rate
from runtime.messaging_policy_alerts.detectors.no_activity import detect_no_activity


def run_alert_detectors(*, metrics, thresholds):
    out = []
    for detector in (
        detect_no_activity,
        detect_high_all_failed_rate,
        detect_high_blocked_trace_rate,
        detect_low_success_rate,
        detect_channel_concentration,
        detect_high_fallback_usage,
        detect_high_attempts_per_trace,
    ):
        item = detector(metrics=metrics, thresholds=thresholds)
        if item is not None:
            out.append(item)
    return tuple(out)

from __future__ import annotations

from runtime.messaging_policy_alerts.alert_builder import build_alert
from runtime.messaging_policy_alerts.alert_code import ALERT_HIGH_ATTEMPTS_PER_TRACE
from runtime.messaging_policy_alerts.alert_level import LEVEL_WARN
from runtime.messaging_policy_alerts.counter_math import average_attempts_per_trace


def detect_high_attempts_per_trace(*, metrics, thresholds):
    value = average_attempts_per_trace(attempts_total=metrics.attempts_total, traces_total=metrics.traces_total)
    threshold = float(thresholds.high_attempts_per_trace)
    if value < threshold:
        return None
    return build_alert(code=ALERT_HIGH_ATTEMPTS_PER_TRACE, level=LEVEL_WARN, title="High attempts per trace", detail="Too many delivery attempts are needed on average per trace.", metric_name="attempts_per_trace", metric_value=value, threshold_value=threshold)

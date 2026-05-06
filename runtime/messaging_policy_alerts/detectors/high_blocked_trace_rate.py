from __future__ import annotations

from runtime.messaging_policy_alerts.alert_builder import build_alert
from runtime.messaging_policy_alerts.alert_code import ALERT_HIGH_BLOCKED_TRACE_RATE
from runtime.messaging_policy_alerts.alert_level import LEVEL_WARN


def detect_high_blocked_trace_rate(*, metrics, thresholds):
    value = float(metrics.blocked_trace_rate)
    threshold = float(thresholds.high_blocked_trace_rate)
    if value < threshold:
        return None
    return build_alert(code=ALERT_HIGH_BLOCKED_TRACE_RATE, level=LEVEL_WARN, title="High blocked trace rate", detail="Blocked channels appear in too many traces.", metric_name="blocked_trace_rate", metric_value=value, threshold_value=threshold)

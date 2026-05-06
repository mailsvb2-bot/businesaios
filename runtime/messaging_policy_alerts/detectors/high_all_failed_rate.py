from __future__ import annotations

from runtime.messaging_policy_alerts.alert_builder import build_alert
from runtime.messaging_policy_alerts.alert_code import ALERT_HIGH_ALL_FAILED_RATE
from runtime.messaging_policy_alerts.alert_level import LEVEL_CRITICAL


def detect_high_all_failed_rate(*, metrics, thresholds):
    value = float(metrics.all_failed_rate)
    threshold = float(thresholds.high_all_failed_rate)
    if value < threshold:
        return None
    return build_alert(code=ALERT_HIGH_ALL_FAILED_RATE, level=LEVEL_CRITICAL, title="High all-failed trace rate", detail="Too many traces ended with all delivery attempts failed.", metric_name="all_failed_rate", metric_value=value, threshold_value=threshold)

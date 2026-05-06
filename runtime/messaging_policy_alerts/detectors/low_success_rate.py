from __future__ import annotations

from runtime.messaging_policy_alerts.alert_builder import build_alert
from runtime.messaging_policy_alerts.alert_code import ALERT_LOW_SUCCESS_RATE
from runtime.messaging_policy_alerts.alert_level import LEVEL_CRITICAL


def detect_low_success_rate(*, metrics, thresholds):
    value = float(metrics.success_rate)
    threshold = float(thresholds.low_success_rate)
    if value >= threshold:
        return None
    return build_alert(code=ALERT_LOW_SUCCESS_RATE, level=LEVEL_CRITICAL, title="Low success rate", detail="Successful delivery traces are below the expected threshold.", metric_name="success_rate", metric_value=value, threshold_value=threshold)

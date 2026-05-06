from __future__ import annotations

from runtime.messaging_policy_alerts.alert_builder import build_alert
from runtime.messaging_policy_alerts.alert_code import ALERT_HIGH_FALLBACK_USAGE
from runtime.messaging_policy_alerts.alert_level import LEVEL_INFO
from runtime.messaging_policy_alerts.counter_math import fallback_usage_rate


def detect_high_fallback_usage(*, metrics, thresholds):
    value = fallback_usage_rate(selected_channel_counts=metrics.selected_channel_counts, delivered_channel_counts=metrics.delivered_channel_counts)
    threshold = float(thresholds.high_fallback_usage_rate)
    if value < threshold:
        return None
    return build_alert(code=ALERT_HIGH_FALLBACK_USAGE, level=LEVEL_INFO, title="High fallback usage", detail="A large share of traces needed fallback execution beyond first selected outcomes.", metric_name="fallback_usage_rate", metric_value=value, threshold_value=threshold)

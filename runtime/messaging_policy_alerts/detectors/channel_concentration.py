from __future__ import annotations

from runtime.messaging_policy_alerts.alert_builder import build_alert
from runtime.messaging_policy_alerts.alert_code import ALERT_CHANNEL_CONCENTRATION
from runtime.messaging_policy_alerts.alert_level import LEVEL_WARN
from runtime.messaging_policy_alerts.counter_math import top_share


def detect_channel_concentration(*, metrics, thresholds):
    value = top_share(metrics.selected_channel_counts)
    threshold = float(thresholds.channel_concentration_rate)
    if value < threshold:
        return None
    return build_alert(code=ALERT_CHANNEL_CONCENTRATION, level=LEVEL_WARN, title="Channel concentration risk", detail="One selected channel dominates too much of the traffic.", metric_name="selected_channel_top_share", metric_value=value, threshold_value=threshold)

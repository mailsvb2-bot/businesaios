from __future__ import annotations

from runtime.messaging_policy_alerts.alert_builder import build_alert
from runtime.messaging_policy_alerts.alert_code import ALERT_NO_ACTIVITY
from runtime.messaging_policy_alerts.alert_level import LEVEL_WARN


def detect_no_activity(*, metrics, thresholds):
    if int(metrics.traces_total) > int(thresholds.no_activity_traces_total):
        return None
    return build_alert(code=ALERT_NO_ACTIVITY, level=LEVEL_WARN, title="No messaging policy activity", detail="No traces found for the selected window.", metric_name="traces_total", metric_value=float(metrics.traces_total), threshold_value=float(thresholds.no_activity_traces_total))

from __future__ import annotations

from runtime.messaging_policy_alerts.alert_result import MessagingPolicyAlertResult
from runtime.messaging_policy_alerts.dashboard_adapter import dashboard_result_to_metrics
from runtime.messaging_policy_alerts.detector_pipeline import run_alert_detectors
from runtime.messaging_policy_alerts.thresholds import MessagingPolicyAlertThresholds


class MessagingPolicyAlertDetector:
    def __init__(self, *, thresholds: MessagingPolicyAlertThresholds | None = None):
        self._thresholds = thresholds or MessagingPolicyAlertThresholds()

    def detect(self, dashboard_result) -> MessagingPolicyAlertResult:
        metrics = dashboard_result_to_metrics(dashboard_result)
        alerts = run_alert_detectors(metrics=metrics, thresholds=self._thresholds)
        return MessagingPolicyAlertResult(alerts=tuple(alerts), traces_total=int(metrics.traces_total))

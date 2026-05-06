from runtime.messaging_policy_alerts.detector import MessagingPolicyAlertDetector
from runtime.messaging_policy_dashboard.result_model import MessagingPolicyDashboardResult


def test_detector_returns_no_activity_alert():
    detector = MessagingPolicyAlertDetector()
    dashboard = MessagingPolicyDashboardResult(
        traces_total=0,
        traces_with_success=0,
        traces_all_failed=0,
        traces_with_blocked=0,
        attempts_total=0,
        success_rate=0.0,
        all_failed_rate=0.0,
        blocked_trace_rate=0.0,
        selected_channel_counts=(),
        delivered_channel_counts=(),
        failed_channel_counts=(),
        blocked_channel_counts=(),
        terminal_reason_counts=(),
    )
    out = detector.detect(dashboard)
    assert len(out.alerts) >= 1
    assert out.alerts[0].code == "no_activity"

from runtime.messaging_policy_alerts.detector import MessagingPolicyAlertDetector
from runtime.messaging_policy_alerts.thresholds import MessagingPolicyAlertThresholds
from runtime.messaging_policy_dashboard.result_model import MessagingPolicyDashboardResult


def test_detector_emits_alerts_for_bad_metrics():
    detector = MessagingPolicyAlertDetector(
        thresholds=MessagingPolicyAlertThresholds(
            high_all_failed_rate=0.20,
            high_blocked_trace_rate=0.10,
            low_success_rate=0.70,
            channel_concentration_rate=0.75,
            high_fallback_usage_rate=0.20,
            high_attempts_per_trace=2.0,
        )
    )
    dashboard = MessagingPolicyDashboardResult(
        traces_total=10,
        traces_with_success=3,
        traces_all_failed=4,
        traces_with_blocked=2,
        attempts_total=30,
        success_rate=0.30,
        all_failed_rate=0.40,
        blocked_trace_rate=0.20,
        selected_channel_counts=(("telegram", 9), ("sms", 1)),
        delivered_channel_counts=(("sms", 3),),
        failed_channel_counts=(("telegram", 7),),
        blocked_channel_counts=(("telegram", 2),),
        terminal_reason_counts=(("all_attempts_failed", 4),),
    )
    out = detector.detect(dashboard)
    assert len(out.alerts) >= 5

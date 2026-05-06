from runtime.messaging_policy_alerts.service import MessagingPolicyAlertService
from runtime.messaging_policy_dashboard.result_model import MessagingPolicyDashboardResult


class _DashboardService:
    def build(self, **kwargs):
        return MessagingPolicyDashboardResult(
            traces_total=5,
            traces_with_success=1,
            traces_all_failed=3,
            traces_with_blocked=1,
            attempts_total=12,
            success_rate=0.20,
            all_failed_rate=0.60,
            blocked_trace_rate=0.20,
            selected_channel_counts=(("whatsapp", 5),),
            delivered_channel_counts=(("sms", 1),),
            failed_channel_counts=(("whatsapp", 4),),
            blocked_channel_counts=(("whatsapp", 1),),
            terminal_reason_counts=(("all_attempts_failed", 3),),
        )


def test_alert_service_builds_alert_result():
    service = MessagingPolicyAlertService(dashboard_service=_DashboardService())
    out = service.build(tenant_id="t1", limit=100)
    assert out.traces_total == 5
    assert len(out.alerts) >= 1

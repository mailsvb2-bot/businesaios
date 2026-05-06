from interfaces.web.debug.messaging_policy_dashboard.json_controller import MessagingPolicyDashboardJsonController
from runtime.messaging_policy_dashboard.result_model import MessagingPolicyDashboardResult


class _Service:
    def build(self, **kwargs):
        return MessagingPolicyDashboardResult(
            traces_total=2, traces_with_success=1, traces_all_failed=1, traces_with_blocked=0,
            attempts_total=3, success_rate=0.5, all_failed_rate=0.5, blocked_trace_rate=0.0,
            selected_channel_counts=(( 'sms', 1),), delivered_channel_counts=(( 'sms', 1),), failed_channel_counts=(( 'telegram', 1),), blocked_channel_counts=(), terminal_reason_counts=(( 'all_attempts_failed', 1),),
        )


def test_json_controller_returns_dashboard():
    ctrl = MessagingPolicyDashboardJsonController(dashboard_service=_Service())
    out = ctrl.get_dashboard(tenant_id='t1', user_id='', date_from='', date_to='', limit=500)
    assert out.status_code == 200
    assert out.body['dashboard']['traces_total'] == 2

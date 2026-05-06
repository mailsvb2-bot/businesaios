from runtime.messaging_policy_dashboard.service import MessagingPolicyDashboardService
from runtime.messaging_policy_trace.summary_record import MessagingPolicyTraceSummary


class _TraceSearch:
    def search(self, **kwargs):
        return (
            MessagingPolicyTraceSummary(
                tenant_id='t1', user_id='u1', correlation_id='c1', decision_id='d1',
                created_at='2026-03-01T10:00:00+00:00', updated_at='2026-03-01T10:05:00+00:00',
                attempts_count=2, selected_channel='email', terminal_reason='', delivered=('email',), failed=('telegram',), blocked=(), last_plan_channels=('telegram', 'email'),
            ),
        )


def test_dashboard_service_builds_result():
    service = MessagingPolicyDashboardService(trace_search_service=_TraceSearch())
    out = service.build(tenant_id='t1', limit=100)
    assert out.traces_total == 1
    assert out.traces_with_success == 1
    assert out.selected_channel_counts[0][0] == 'email'

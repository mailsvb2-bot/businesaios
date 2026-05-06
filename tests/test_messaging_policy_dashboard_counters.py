from runtime.messaging_policy_dashboard.aggregator import MessagingPolicyDashboardAggregator
from runtime.messaging_policy_trace.summary_record import MessagingPolicyTraceSummary


def test_aggregator_builds_counts_and_rates():
    agg = MessagingPolicyDashboardAggregator()
    result = agg.aggregate([
        MessagingPolicyTraceSummary(
            tenant_id='t1', user_id='u1', correlation_id='c1', decision_id='d1',
            created_at='2026-03-01T10:00:00+00:00', updated_at='2026-03-01T10:05:00+00:00',
            attempts_count=2, selected_channel='sms', terminal_reason='', delivered=('sms',), failed=('telegram',), blocked=(), last_plan_channels=('telegram', 'sms'),
        ),
        MessagingPolicyTraceSummary(
            tenant_id='t1', user_id='u2', correlation_id='c2', decision_id='d2',
            created_at='2026-03-01T11:00:00+00:00', updated_at='2026-03-01T11:03:00+00:00',
            attempts_count=1, selected_channel='', terminal_reason='all_attempts_failed', delivered=(), failed=('whatsapp',), blocked=('whatsapp',), last_plan_channels=('whatsapp',),
        ),
    ])
    assert result.traces_total == 2
    assert result.traces_with_success == 1
    assert result.traces_all_failed == 1
    assert result.traces_with_blocked == 1
    assert result.attempts_total == 3

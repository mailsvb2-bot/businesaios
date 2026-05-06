from __future__ import annotations

from runtime.messaging_policy_dashboard.channel_counters import ChannelCounters
from runtime.messaging_policy_dashboard.kpi_state import DashboardKPIState
from runtime.messaging_policy_dashboard.kpi_updater import update_kpis
from runtime.messaging_policy_dashboard.rate_math import safe_rate
from runtime.messaging_policy_dashboard.result_model import MessagingPolicyDashboardResult
from runtime.messaging_policy_dashboard.terminal_reason_counter import TerminalReasonCounter


class MessagingPolicyDashboardAggregator:
    def aggregate(self, summaries) -> MessagingPolicyDashboardResult:
        channel_counters = ChannelCounters()
        terminal_reasons = TerminalReasonCounter()
        kpis = DashboardKPIState()

        for summary in tuple(summaries or ()):
            update_kpis(state=kpis, summary=summary)
            channel_counters.add_selected(str(summary.selected_channel or ''))
            channel_counters.add_delivered_many(summary.delivered)
            channel_counters.add_failed_many(summary.failed)
            channel_counters.add_blocked_many(summary.blocked)
            terminal_reasons.add(str(summary.terminal_reason or ''))

        selected = tuple((item['channel'], item['count']) for item in channel_counters.as_dict()['selected'])
        delivered = tuple((item['channel'], item['count']) for item in channel_counters.as_dict()['delivered'])
        failed = tuple((item['channel'], item['count']) for item in channel_counters.as_dict()['failed'])
        blocked = tuple((item['channel'], item['count']) for item in channel_counters.as_dict()['blocked'])
        reasons = tuple((item['reason'], item['count']) for item in terminal_reasons.as_list())

        return MessagingPolicyDashboardResult(
            traces_total=int(kpis.traces_total),
            traces_with_success=int(kpis.traces_with_success),
            traces_all_failed=int(kpis.traces_all_failed),
            traces_with_blocked=int(kpis.traces_with_blocked),
            attempts_total=int(kpis.attempts_total),
            success_rate=safe_rate(kpis.traces_with_success, kpis.traces_total),
            all_failed_rate=safe_rate(kpis.traces_all_failed, kpis.traces_total),
            blocked_trace_rate=safe_rate(kpis.traces_with_blocked, kpis.traces_total),
            selected_channel_counts=selected,
            delivered_channel_counts=delivered,
            failed_channel_counts=failed,
            blocked_channel_counts=blocked,
            terminal_reason_counts=reasons,
        )

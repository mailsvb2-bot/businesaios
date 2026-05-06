from __future__ import annotations

from runtime.messaging_policy_alerts.dashboard_metrics import MessagingPolicyDashboardMetrics


def dashboard_result_to_metrics(result) -> MessagingPolicyDashboardMetrics:
    return MessagingPolicyDashboardMetrics(
        traces_total=int(result.traces_total),
        success_rate=float(result.success_rate),
        all_failed_rate=float(result.all_failed_rate),
        blocked_trace_rate=float(result.blocked_trace_rate),
        attempts_total=int(result.attempts_total),
        selected_channel_counts=tuple(result.selected_channel_counts),
        delivered_channel_counts=tuple(result.delivered_channel_counts),
        failed_channel_counts=tuple(result.failed_channel_counts),
        blocked_channel_counts=tuple(result.blocked_channel_counts),
        terminal_reason_counts=tuple(result.terminal_reason_counts),
    )

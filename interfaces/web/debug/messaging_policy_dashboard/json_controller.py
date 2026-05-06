from __future__ import annotations

from interfaces.web.debug.common.http_response import HttpResponse


def _pairs_to_dicts(items, *, key_name: str) -> list[dict]:
    return [{key_name: key, 'count': value} for key, value in tuple(items or ())]


def result_to_dict(result) -> dict:
    return {
        'traces_total': result.traces_total,
        'traces_with_success': result.traces_with_success,
        'traces_all_failed': result.traces_all_failed,
        'traces_with_blocked': result.traces_with_blocked,
        'attempts_total': result.attempts_total,
        'success_rate': result.success_rate,
        'all_failed_rate': result.all_failed_rate,
        'blocked_trace_rate': result.blocked_trace_rate,
        'selected_channel_counts': _pairs_to_dicts(result.selected_channel_counts, key_name='channel'),
        'delivered_channel_counts': _pairs_to_dicts(result.delivered_channel_counts, key_name='channel'),
        'failed_channel_counts': _pairs_to_dicts(result.failed_channel_counts, key_name='channel'),
        'blocked_channel_counts': _pairs_to_dicts(result.blocked_channel_counts, key_name='channel'),
        'terminal_reason_counts': _pairs_to_dicts(result.terminal_reason_counts, key_name='reason'),
    }


class MessagingPolicyDashboardJsonController:
    def __init__(self, *, dashboard_service):
        self._dashboard_service = dashboard_service

    def get_dashboard(self, *, tenant_id: str, user_id: str, date_from: str, date_to: str, limit: int) -> HttpResponse:
        result = self._dashboard_service.build(
            tenant_id=tenant_id,
            user_id=user_id,
            date_from=date_from,
            date_to=date_to,
            limit=limit,
        )
        return HttpResponse(status_code=200, content_type='application/json', body={'ok': True, 'dashboard': result_to_dict(result)})

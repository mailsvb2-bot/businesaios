from __future__ import annotations

from interfaces.web.debug.common.http_response import HttpResponse


def summary_to_dict(item) -> dict:
    return {
        'tenant_id': item.tenant_id,
        'user_id': item.user_id,
        'correlation_id': item.correlation_id,
        'decision_id': item.decision_id,
        'created_at': item.created_at,
        'updated_at': item.updated_at,
        'attempts_count': item.attempts_count,
        'selected_channel': item.selected_channel,
        'terminal_reason': item.terminal_reason,
        'delivered': list(item.delivered),
        'failed': list(item.failed),
        'blocked': list(item.blocked),
        'last_plan_channels': list(item.last_plan_channels),
        'snapshot_url': (
            '/api/debug/messaging-policy-snapshot'
            f'?tenant_id={item.tenant_id}&user_id={item.user_id}&correlation_id={item.correlation_id}'
        ),
        'snapshot_html_url': (
            '/debug/messaging-policy-snapshot'
            f'?tenant_id={item.tenant_id}&user_id={item.user_id}&correlation_id={item.correlation_id}'
        ),
    }


class MessagingPolicyTraceSearchJsonController:
    def __init__(self, *, search_service):
        self._search_service = search_service

    def search(self, *, tenant_id: str, user_id: str, date_from: str, date_to: str, limit: int) -> HttpResponse:
        items = self._search_service.search(
            tenant_id=tenant_id,
            user_id=user_id,
            date_from=date_from,
            date_to=date_to,
            limit=limit,
        )
        return HttpResponse(
            status_code=200,
            content_type='application/json',
            body={'ok': True, 'items': [summary_to_dict(item) for item in items], 'count': len(items)},
        )

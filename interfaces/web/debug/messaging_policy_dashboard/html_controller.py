from __future__ import annotations

from interfaces.web.debug.common.html_escape import esc
from interfaces.web.debug.common.http_response import HttpResponse
from interfaces.web.debug.messaging_policy_dashboard.json_controller import result_to_dict


def _metric_card(*, title: str, value) -> str:
    return (
        "<div style='border:1px solid #ddd;border-radius:12px;padding:16px;min-width:180px;'>"
        f"<div style='font-size:12px;color:#666;'>{esc(title)}</div>"
        f"<div style='font-size:28px;font-weight:700;margin-top:8px;'>{esc(value)}</div>"
        '</div>'
    )


def _list_block(*, title: str, key_name: str, items) -> str:
    rows = []
    for item in list(items or ()):
        rows.append('<tr>' f"<td>{esc(item.get(key_name))}</td>" f"<td>{esc(item.get('count'))}</td>" '</tr>')
    if not rows:
        rows.append("<tr><td colspan='2'><em>empty</em></td></tr>")
    return (
        "<div style='border:1px solid #ddd;border-radius:12px;padding:16px;margin-top:16px;'>"
        f"<h3 style='margin-top:0;'>{esc(title)}</h3>"
        "<table border='1' cellpadding='8' cellspacing='0' style='border-collapse:collapse;width:100%;'>"
        '<thead><tr>'
        f"<th>{esc(key_name)}</th><th>count</th>"
        '</tr></thead><tbody>'
        + ''.join(rows)
        + '</tbody></table></div>'
    )


def build_dashboard_html(result, *, tenant_id: str, user_id: str, date_from: str, date_to: str) -> str:
    data = result_to_dict(result)
    metrics = (
        "<div style='display:flex;gap:12px;flex-wrap:wrap;'>"
        + _metric_card(title='traces_total', value=data['traces_total'])
        + _metric_card(title='attempts_total', value=data['attempts_total'])
        + _metric_card(title='success_rate', value=data['success_rate'])
        + _metric_card(title='all_failed_rate', value=data['all_failed_rate'])
        + _metric_card(title='blocked_trace_rate', value=data['blocked_trace_rate'])
        + '</div>'
    )
    return (
        "<!doctype html><html><head><meta charset='utf-8'><title>Messaging Policy Dashboard</title></head>"
        "<body style='font-family:Arial,sans-serif;padding:24px;'>"
        '<h1>Messaging Policy Dashboard</h1>'
        f"<p><strong>tenant_id:</strong> {esc(tenant_id)} "
        f"<strong>user_id:</strong> {esc(user_id)} "
        f"<strong>date_from:</strong> {esc(date_from)} "
        f"<strong>date_to:</strong> {esc(date_to)}</p>"
        f'{metrics}'
        f"{_list_block(title='Selected channel counts', key_name='channel', items=data['selected_channel_counts'])}"
        f"{_list_block(title='Delivered channel counts', key_name='channel', items=data['delivered_channel_counts'])}"
        f"{_list_block(title='Failed channel counts', key_name='channel', items=data['failed_channel_counts'])}"
        f"{_list_block(title='Blocked channel counts', key_name='channel', items=data['blocked_channel_counts'])}"
        f"{_list_block(title='Terminal reason counts', key_name='reason', items=data['terminal_reason_counts'])}"
        '</body></html>'
    )


class MessagingPolicyDashboardHtmlController:
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
        return HttpResponse(
            status_code=200,
            content_type='text/html; charset=utf-8',
            body=build_dashboard_html(result, tenant_id=tenant_id, user_id=user_id, date_from=date_from, date_to=date_to),
        )

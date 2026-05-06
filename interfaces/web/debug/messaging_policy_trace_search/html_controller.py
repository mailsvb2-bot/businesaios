from __future__ import annotations

from interfaces.web.debug.common.html_escape import esc
from interfaces.web.debug.common.http_response import HttpResponse


def _build_rows(items) -> str:
    rows = []
    for item in list(items or ()):
        rows.append(
            '<tr>'
            f'<td>{esc(item.created_at)}</td>'
            f'<td>{esc(item.updated_at)}</td>'
            f'<td>{esc(item.user_id)}</td>'
            f'<td>{esc(item.correlation_id)}</td>'
            f'<td>{esc(item.selected_channel)}</td>'
            f'<td>{esc(item.terminal_reason)}</td>'
            f'<td>{esc(item.attempts_count)}</td>'
            f"<td><a href='/debug/messaging-policy-snapshot?tenant_id={esc(item.tenant_id)}&user_id={esc(item.user_id)}&correlation_id={esc(item.correlation_id)}'>open</a></td>"
            '</tr>'
        )
    return ''.join(rows)


def build_table(items) -> str:
    return (
        "<table border='1' cellpadding='8' cellspacing='0'>"
        '<thead><tr>'
        '<th>created_at</th><th>updated_at</th><th>user_id</th><th>correlation_id</th><th>selected_channel</th><th>terminal_reason</th><th>attempts</th><th>snapshot</th>'
        '</tr></thead><tbody>'
        f'{_build_rows(items)}'
        '</tbody></table>'
    )


class MessagingPolicyTraceSearchHtmlController:
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
        body = (
            "<!doctype html><html><head><meta charset='utf-8'><title>Messaging Policy Trace Search</title></head>"
            "<body style='font-family: Arial, sans-serif; padding: 24px;'>"
            '<h1>Messaging Policy Trace Search</h1>'
            f"<p><strong>tenant_id:</strong> {esc(tenant_id)} <strong>user_id:</strong> {esc(user_id)} <strong>date_from:</strong> {esc(date_from)} <strong>date_to:</strong> {esc(date_to)}</p>"
            f'{build_table(items)}'
            '</body></html>'
        )
        return HttpResponse(status_code=200, content_type='text/html; charset=utf-8', body=body)

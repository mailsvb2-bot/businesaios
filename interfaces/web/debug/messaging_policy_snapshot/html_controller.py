from __future__ import annotations

from interfaces.web.debug.common.html_escape import esc
from interfaces.web.debug.common.http_response import HttpResponse


def _build_list(items) -> str:
    values = list(items or ())
    if not values:
        return '<em>empty</em>'
    return '<ul>' + ''.join(f'<li>{esc(item)}</li>' for item in values) + '</ul>'


def _build_kv_row(*, key: str, value_html: str) -> str:
    return '<tr>' f'<th>{esc(key)}</th>' f'<td>{value_html}</td>' '</tr>'


def build_snapshot_html(snapshot: dict | None, *, tenant_id: str, user_id: str, correlation_id: str) -> str:
    header = (
        '<h1>Messaging Policy Snapshot</h1>'
        f'<p><strong>tenant_id:</strong> {esc(tenant_id)}<br>'
        f'<strong>user_id:</strong> {esc(user_id)}<br>'
        f'<strong>correlation_id:</strong> {esc(correlation_id)}</p>'
    )
    if snapshot is None:
        body = '<p>Snapshot not found.</p>'
    else:
        body = (
            "<table border='1' cellpadding='8' cellspacing='0'>"
            + _build_kv_row(key='last_selected_channel', value_html=esc(snapshot.get('last_selected_channel')))
            + _build_kv_row(key='last_terminal_reason', value_html=esc(snapshot.get('last_terminal_reason')))
            + _build_kv_row(key='attempts_count', value_html=esc(snapshot.get('attempts_count')))
            + _build_kv_row(key='delivered', value_html=_build_list(snapshot.get('delivered')))
            + _build_kv_row(key='failed', value_html=_build_list(snapshot.get('failed')))
            + _build_kv_row(key='blocked', value_html=_build_list(snapshot.get('blocked')))
            + _build_kv_row(key='last_plan_channels', value_html=_build_list(snapshot.get('last_plan_channels')))
            + '</table>'
        )
    return (
        "<!doctype html><html><head><meta charset='utf-8'><title>Messaging Policy Snapshot</title></head>"
        "<body style='font-family: Arial, sans-serif; padding: 24px;'>"
        f'{header}{body}'
        '</body></html>'
    )


class MessagingPolicySnapshotHtmlController:
    def __init__(self, *, api_service):
        self._api_service = api_service

    def get_snapshot_page(self, *, tenant_id: str, user_id: str, correlation_id: str) -> HttpResponse:
        snapshot = self._api_service.get_snapshot(
            tenant_id=tenant_id,
            user_id=user_id,
            correlation_id=correlation_id,
        )
        return HttpResponse(
            status_code=200 if snapshot is not None else 404,
            content_type='text/html; charset=utf-8',
            body=build_snapshot_html(snapshot, tenant_id=tenant_id, user_id=user_id, correlation_id=correlation_id),
        )

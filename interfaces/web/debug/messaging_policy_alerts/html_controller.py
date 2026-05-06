from __future__ import annotations

from interfaces.web.debug.common.html_escape import esc
from interfaces.web.debug.common.http_response import HttpResponse


def _alert_to_dict(item) -> dict:
    return {
        "code": item.code,
        "level": item.level,
        "title": item.title,
        "detail": item.detail,
        "metric_name": item.metric_name,
        "metric_value": item.metric_value,
        "threshold_value": item.threshold_value,
    }


def _build_rows(items) -> str:
    rows = []
    for item in list(items or ()):
        rows.append(
            "<tr>"
            f"<td>{esc(item['code'])}</td>"
            f"<td>{esc(item['level'])}</td>"
            f"<td>{esc(item['title'])}</td>"
            f"<td>{esc(item['detail'])}</td>"
            f"<td>{esc(item['metric_name'])}</td>"
            f"<td>{esc(item['metric_value'])}</td>"
            f"<td>{esc(item['threshold_value'])}</td>"
            "</tr>"
        )
    if not rows:
        rows.append("<tr><td colspan='7'><em>no alerts</em></td></tr>")
    return "".join(rows)


class MessagingPolicyAlertsHtmlController:
    def __init__(self, *, alert_service):
        self._alert_service = alert_service

    def get_alerts(self, *, tenant_id: str, user_id: str, date_from: str, date_to: str, limit: int) -> HttpResponse:
        result = self._alert_service.build(
            tenant_id=tenant_id,
            user_id=user_id,
            date_from=date_from,
            date_to=date_to,
            limit=limit,
        )
        items = [_alert_to_dict(item) for item in result.alerts]
        body = (
            "<!doctype html><html><head><meta charset='utf-8'><title>Messaging Policy Alerts</title></head>"
            "<body style='font-family:Arial,sans-serif;padding:24px;'>"
            "<h1>Messaging Policy Alerts</h1>"
            f"<p><strong>tenant_id:</strong> {esc(tenant_id)} "
            f"<strong>user_id:</strong> {esc(user_id)} "
            f"<strong>date_from:</strong> {esc(date_from)} "
            f"<strong>date_to:</strong> {esc(date_to)} "
            f"<strong>traces_total:</strong> {esc(result.traces_total)}</p>"
            "<table border='1' cellpadding='8' cellspacing='0' style='border-collapse:collapse;width:100%;'>"
            "<thead><tr>"
            "<th>code</th><th>level</th><th>title</th><th>detail</th><th>metric</th><th>value</th><th>threshold</th>"
            "</tr></thead><tbody>"
            f"{_build_rows(items)}"
            "</tbody></table>"
            "</body></html>"
        )
        return HttpResponse(status_code=200, content_type="text/html; charset=utf-8", body=body)

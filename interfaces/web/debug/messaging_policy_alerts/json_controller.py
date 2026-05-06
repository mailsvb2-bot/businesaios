from __future__ import annotations

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


class MessagingPolicyAlertsJsonController:
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
        return HttpResponse(
            status_code=200,
            content_type="application/json",
            body={
                "ok": True,
                "traces_total": result.traces_total,
                "alerts": [_alert_to_dict(item) for item in result.alerts],
                "count": len(result.alerts),
            },
        )

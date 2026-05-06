from __future__ import annotations

from interfaces.web.debug.common.query_utils import clean_text, clamp_int
from interfaces.web.debug.messaging_policy_alerts.html_controller import MessagingPolicyAlertsHtmlController
from interfaces.web.debug.messaging_policy_alerts.json_controller import MessagingPolicyAlertsJsonController


def parse_alert_query(
    *,
    tenant_id: object | None,
    user_id: object | None,
    date_from: object | None,
    date_to: object | None,
    limit: object | None,
) -> dict:
    return {
        "tenant_id": clean_text(tenant_id, default="default"),
        "user_id": clean_text(user_id),
        "date_from": clean_text(date_from),
        "date_to": clean_text(date_to),
        "limit": clamp_int(limit, default=500, lower=1, upper=5000),
    }


class MessagingPolicyAlertsRouteBundle:
    def __init__(self, *, alert_service):
        self.alert_service = alert_service
        self._json = MessagingPolicyAlertsJsonController(alert_service=alert_service)
        self._html = MessagingPolicyAlertsHtmlController(alert_service=alert_service)

    def json(self, *, tenant_id, user_id, date_from, date_to, limit):
        query = parse_alert_query(tenant_id=tenant_id, user_id=user_id, date_from=date_from, date_to=date_to, limit=limit)
        return self._json.get_alerts(**query)

    def html(self, *, tenant_id, user_id, date_from, date_to, limit):
        query = parse_alert_query(tenant_id=tenant_id, user_id=user_id, date_from=date_from, date_to=date_to, limit=limit)
        return self._html.get_alerts(**query)

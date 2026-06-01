from __future__ import annotations

from interfaces.web.debug.common.query_utils import clamp_int, clean_text
from interfaces.web.debug.messaging_policy_dashboard.html_controller import MessagingPolicyDashboardHtmlController
from interfaces.web.debug.messaging_policy_dashboard.json_controller import MessagingPolicyDashboardJsonController


def parse_dashboard_query(
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


class MessagingPolicyDashboardRouteBundle:
    def __init__(self, *, dashboard_service):
        self._json = MessagingPolicyDashboardJsonController(dashboard_service=dashboard_service)
        self._html = MessagingPolicyDashboardHtmlController(dashboard_service=dashboard_service)

    def json(self, *, tenant_id, user_id, date_from, date_to, limit):
        query = parse_dashboard_query(tenant_id=tenant_id, user_id=user_id, date_from=date_from, date_to=date_to, limit=limit)
        return self._json.get_dashboard(**query)

    def html(self, *, tenant_id, user_id, date_from, date_to, limit):
        query = parse_dashboard_query(tenant_id=tenant_id, user_id=user_id, date_from=date_from, date_to=date_to, limit=limit)
        return self._html.get_dashboard(**query)

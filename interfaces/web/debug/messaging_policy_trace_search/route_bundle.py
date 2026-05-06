from __future__ import annotations

from interfaces.web.debug.messaging_policy_trace_search.html_controller import MessagingPolicyTraceSearchHtmlController
from interfaces.web.debug.messaging_policy_trace_search.json_controller import MessagingPolicyTraceSearchJsonController
from interfaces.web.debug.messaging_policy_trace_search.query_parser import parse_trace_search_query


class MessagingPolicyTraceSearchRouteBundle:
    def __init__(self, *, search_service):
        self._json = MessagingPolicyTraceSearchJsonController(search_service=search_service)
        self._html = MessagingPolicyTraceSearchHtmlController(search_service=search_service)

    def json(self, *, tenant_id, user_id, date_from, date_to, limit):
        query = parse_trace_search_query(tenant_id=tenant_id, user_id=user_id, date_from=date_from, date_to=date_to, limit=limit)
        return self._json.search(
            tenant_id=query.tenant_id,
            user_id=query.user_id,
            date_from=query.date_from,
            date_to=query.date_to,
            limit=query.limit,
        )

    def html(self, *, tenant_id, user_id, date_from, date_to, limit):
        query = parse_trace_search_query(tenant_id=tenant_id, user_id=user_id, date_from=date_from, date_to=date_to, limit=limit)
        return self._html.search(
            tenant_id=query.tenant_id,
            user_id=query.user_id,
            date_from=query.date_from,
            date_to=query.date_to,
            limit=query.limit,
        )

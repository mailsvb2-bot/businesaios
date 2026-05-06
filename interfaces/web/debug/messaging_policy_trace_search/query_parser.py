from __future__ import annotations

from interfaces.web.debug.common.query_utils import clean_text, clamp_int
from interfaces.web.debug.messaging_policy_trace_search.query_model import TraceSearchQuery


def parse_trace_search_query(*, tenant_id: object | None, user_id: object | None, date_from: object | None, date_to: object | None, limit: object | None) -> TraceSearchQuery:
    return TraceSearchQuery(
        tenant_id=clean_text(tenant_id, default='default'),
        user_id=clean_text(user_id),
        date_from=clean_text(date_from),
        date_to=clean_text(date_to),
        limit=clamp_int(limit, default=50, lower=1, upper=200),
    )

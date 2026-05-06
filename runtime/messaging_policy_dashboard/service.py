from __future__ import annotations

from runtime.tenancy import normalize_tenant_scope
from runtime.messaging_policy_dashboard.aggregator import MessagingPolicyDashboardAggregator


class MessagingPolicyDashboardService:
    def __init__(self, *, trace_search_service, aggregator: MessagingPolicyDashboardAggregator | None = None):
        self._trace_search_service = trace_search_service
        self._aggregator = aggregator or MessagingPolicyDashboardAggregator()

    def build(
        self,
        *,
        tenant_id: str,
        user_id: str = '',
        date_from: str = '',
        date_to: str = '',
        limit: int = 500,
    ):
        tenant_scope = normalize_tenant_scope(tenant_id, allow_unknown=True)
        summaries = self._trace_search_service.search(
            tenant_id=tenant_scope,
            user_id=str(user_id or ''),
            date_from=str(date_from or ''),
            date_to=str(date_to or ''),
            limit=int(limit),
        )
        return self._aggregator.aggregate(summaries)

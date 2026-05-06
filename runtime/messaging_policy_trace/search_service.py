from __future__ import annotations

from runtime.tenancy import normalize_tenant_scope
from runtime.messaging_policy_trace.group_records import group_records
from runtime.messaging_policy_trace.summary_builder import MessagingPolicyTraceSummaryBuilder
from runtime.messaging_policy_trace.summary_sort import sort_summaries_desc


class MessagingPolicyTraceSearchService:
    def __init__(self, *, search_store, summary_builder: MessagingPolicyTraceSummaryBuilder | None = None):
        self._search_store = search_store
        self._summary_builder = summary_builder or MessagingPolicyTraceSummaryBuilder()

    def search(self, *, tenant_id: str, user_id: str = '', date_from: str = '', date_to: str = '', limit: int = 50):
        tenant_scope = normalize_tenant_scope(tenant_id, allow_unknown=True)
        records = self._search_store.search_records(
            tenant_id=tenant_scope,
            user_id=str(user_id),
            date_from=str(date_from or ''),
            date_to=str(date_to or ''),
        )
        summaries = []
        for bucket in group_records(records):
            summary = self._summary_builder.build_one(bucket.records)
            if summary is not None:
                summaries.append(summary)
        items = sort_summaries_desc(summaries)
        return items[: max(0, int(limit or 0))]

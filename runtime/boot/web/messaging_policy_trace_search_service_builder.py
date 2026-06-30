from __future__ import annotations

from runtime.messaging_policy_trace.search_service import MessagingPolicyTraceSearchService
from runtime.messaging_policy_trace.search_store import MessagingPolicyTraceSearchStore

CANON_BOOT_WIRING_ONLY = True

def build_messaging_policy_trace_search_service(*, event_store) -> MessagingPolicyTraceSearchService:
    return MessagingPolicyTraceSearchService(
        search_store=MessagingPolicyTraceSearchStore(event_store=event_store)
    )


__all__ = ["build_messaging_policy_trace_search_service"]

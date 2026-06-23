from __future__ import annotations

CANON_BOOT_WIRING_ONLY = True

from runtime.messaging_policy_trace.search_service import MessagingPolicyTraceSearchService
from runtime.messaging_policy_trace.search_store import MessagingPolicyTraceSearchStore


def build_messaging_policy_trace_search_service(*, event_store) -> MessagingPolicyTraceSearchService:
    return MessagingPolicyTraceSearchService(
        search_store=MessagingPolicyTraceSearchStore(event_store=event_store)
    )


__all__ = ["build_messaging_policy_trace_search_service"]

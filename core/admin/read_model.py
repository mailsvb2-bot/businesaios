from __future__ import annotations

"""Admin read-model facade.

The implementation lives in small focused modules to keep admin analytics
auditable and to avoid a single read-model god module.
"""

from core.admin.read_models import (
    ab_offers_summary,
    demo_summary,
    funnel2_report,
    funnel_counts,
    giftshare_summary,
    health_brief,
    latency_brief,
    latency_breakdown,
    pricing_change_requests,
    retention_brief,
    segments_summary,
    sla_breaches_brief,
    users_today,
)

__all__ = [
    "users_today",
    "funnel_counts",
    "demo_summary",
    "retention_brief",
    "health_brief",
    "segments_summary",
    "funnel2_report",
    "ab_offers_summary",
    "giftshare_summary",
    "pricing_change_requests",
    "latency_brief",
    "latency_breakdown",
    "sla_breaches_brief",
]

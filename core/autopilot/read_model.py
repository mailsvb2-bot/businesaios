from __future__ import annotations

"""Business observability read-models.

These are intentionally simple and derived from event log.
They power the Telegram "dashboards".
"""

from typing import Any, Optional
from collections.abc import Mapping

from core.autopilot.read_model_support import (
    collect_ads_metrics,
    collect_recent_autopilot_action_rows,
    collect_revenue_and_users,
    collect_unique_users,
    day_start_ms_utc,
    today_start_ms,
    utc_now_ms,
)


def business_metrics_window(
    event_store: Any,
    *,
    tenant_id: str = "default",
    days: int = 7,
    lead_event_type: str = "lead_created@v1",
    purchase_event_type: str = "purchase_completed@v1",
    now_ms: int | None = None,
) -> list[dict[str, int]]:
    """Compute a rolling window of daily business metrics (UTC days).

    Returns oldest->newest for easier window evaluation.

    Each item includes (best-effort):
      profit_minor, cac_minor, spend_minor, conversions

    `now_ms` makes the read-model deterministic for tests/replay and prevents
    "second timeline" drift inside one evaluation pass.
    """

    out: list[dict[str, int]] = []
    if event_store is None or not hasattr(event_store, "iter_events"):
        return out

    now_ms_resolved = utc_now_ms(now_ms=now_ms)
    days = max(1, int(days))
    for i in range(days, 0, -1):
        start_ms = day_start_ms_utc(days_ago=i - 1, now_ms=now_ms_resolved)
        end_ms = now_ms_resolved if i == 1 else day_start_ms_utc(days_ago=i - 2, now_ms=now_ms_resolved)

        leads_u = collect_unique_users(
            event_store=event_store,
            tenant_id=tenant_id,
            start_ms=start_ms,
            end_ms=end_ms,
            event_type=str(lead_event_type),
        )

        purchases_u, revenue_minor = collect_revenue_and_users(
            event_store=event_store,
            tenant_id=tenant_id,
            start_ms=start_ms,
            end_ms=end_ms,
            event_type=str(purchase_event_type),
            amount_key="amount_minor",
        )
        if not purchases_u:
            purchases_u, revenue_minor = collect_revenue_and_users(
                event_store=event_store,
                tenant_id=tenant_id,
                start_ms=start_ms,
                end_ms=end_ms,
                event_type="payment_succeeded",
                amount_key="amount",
            )

        ads = collect_ads_metrics(
            event_store=event_store,
            tenant_id=tenant_id,
            start_ms=start_ms,
            end_ms=end_ms,
        )
        out.append({
            "day_start_ms": int(start_ms),
            "leads": int(len(leads_u)),
            "purchases": int(len(purchases_u)),
            "revenue_minor": int(revenue_minor),
            "profit_minor": int(revenue_minor),
            "cac_minor": 0,
            "spend_minor": int(ads["spend_minor"]),
            "conversions": int(ads["conversions"]),
        })

    return out


def today_business_metrics(
    event_store: Any,
    *,
    tenant_id: str = "default",
    lead_event_type: str = "lead_created@v1",
    purchase_event_type: str = "purchase_completed@v1",
    now_ms: int | None = None,
) -> dict[str, int]:
    """Compute business metrics for today.

    This is best-effort: if your product emits only payment events,
    purchases will be approximated by payment_succeeded.
    """

    if event_store is None or not hasattr(event_store, "iter_events"):
        return {"leads": 0, "purchases": 0, "revenue_minor": 0, "profit_minor": 0, "cac_minor": 0}

    now_ms_resolved = utc_now_ms(now_ms=now_ms)
    start_ms = today_start_ms(now_ms=now_ms_resolved)

    leads_u = collect_unique_users(
        event_store=event_store,
        tenant_id=tenant_id,
        start_ms=start_ms,
        end_ms=now_ms_resolved,
        event_type=str(lead_event_type),
    )

    purchases_u, revenue_minor = collect_revenue_and_users(
        event_store=event_store,
        tenant_id=tenant_id,
        start_ms=start_ms,
        end_ms=now_ms_resolved,
        event_type=str(purchase_event_type),
        amount_key="amount_minor",
    )
    if not purchases_u:
        purchases_u, revenue_minor = collect_revenue_and_users(
            event_store=event_store,
            tenant_id=tenant_id,
            start_ms=start_ms,
            end_ms=now_ms_resolved,
            event_type="payment_succeeded",
            amount_key="amount",
        )

    return {
        "leads": int(len(leads_u)),
        "purchases": int(len(purchases_u)),
        "revenue_minor": int(revenue_minor),
        "profit_minor": int(revenue_minor),
        "cac_minor": 0,
    }


def recent_autopilot_actions(
    event_store: Any,
    *,
    tenant_id: str = "default",
    days: int = 7,
    now_ms: int | None = None,
) -> list[Mapping[str, Any]]:
    if event_store is None or not hasattr(event_store, "iter_events"):
        return []
    now_ms_resolved = utc_now_ms(now_ms=now_ms)
    start_ms = max(0, now_ms_resolved - int(days) * 24 * 3600 * 1000)
    return collect_recent_autopilot_action_rows(
        event_store=event_store,
        tenant_id=tenant_id,
        start_ms=start_ms,
        end_ms=now_ms_resolved,
    )

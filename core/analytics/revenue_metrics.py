from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from typing import Any, Iterable, Protocol

from config.revenue_metrics_policy import DEFAULT_REVENUE_METRICS_POLICY, RevenueMetricsPolicy
from core.contracts.event_types import OFFER_CLICKED, OFFER_SHOWN, PURCHASE_FAILED, PURCHASE_SUCCESS


class EventStore(Protocol):
    def latest_events(self, *, tenant_id: str, limit: int = DEFAULT_REVENUE_METRICS_POLICY.latest_events_limit) -> list[dict]: ...


def _to_utc_dt(ts: Any, *, policy: RevenueMetricsPolicy = DEFAULT_REVENUE_METRICS_POLICY) -> datetime | None:
    if ts is None:
        return None
    if isinstance(ts, datetime):
        return ts.astimezone(UTC)
    try:
        if isinstance(ts, (int, float)):
            v = float(ts)
            if v > float(policy.epoch_millis_threshold):
                return datetime.fromtimestamp(v / float(policy.zero_amount + 1000), tz=UTC)
            return datetime.fromtimestamp(v, tz=UTC)
        s = str(ts).replace("Z", "+00:00")
        dt = datetime.fromisoformat(s)
        return dt.astimezone(UTC)
    except Exception:
        return None


@dataclass(frozen=True)
class RevenueWindow:
    day: date
    start_utc: datetime
    end_utc: datetime


def make_yesterday_window(
    now_utc: datetime,
    *,
    policy: RevenueMetricsPolicy = DEFAULT_REVENUE_METRICS_POLICY,
) -> RevenueWindow:
    now_utc = now_utc.astimezone(UTC)
    end = datetime(now_utc.year, now_utc.month, now_utc.day, tzinfo=UTC)
    start = end - timedelta(days=int(policy.window_days))
    return RevenueWindow(day=start.date(), start_utc=start, end_utc=end)


def aggregate_revenue_metrics(
    *,
    events: Iterable[dict],
    window: RevenueWindow,
    policy: RevenueMetricsPolicy = DEFAULT_REVENUE_METRICS_POLICY,
) -> dict[str, Any]:
    impressions = clicks = ps = pf = 0
    revenue = float(policy.zero_amount)
    offer_revenue: dict[str, float] = {}

    for e in events:
        if not isinstance(e, dict):
            continue
        et = e.get("event_type")
        ts = _to_utc_dt(
            e.get("ts")
            or e.get("created_at")
            or e.get("time")
            or e.get("timestamp")
            or e.get("timestamp_ms"),
            policy=policy,
        )
        if ts is None or ts < window.start_utc or ts >= window.end_utc:
            continue

        payload = e.get("payload") or {}
        offer_id = payload.get("offer_id")

        if et == OFFER_SHOWN:
            impressions += 1
        elif et == OFFER_CLICKED:
            clicks += 1
        elif et == PURCHASE_SUCCESS:
            ps += 1
            amount = float(payload.get("amount", policy.zero_amount) or policy.zero_amount)
            revenue += amount
            if offer_id:
                oid = str(offer_id)
                offer_revenue[oid] = offer_revenue.get(oid, float(policy.zero_amount)) + amount
        elif et == PURCHASE_FAILED:
            pf += 1

    ctr = (clicks / impressions) if impressions > 0 else float(policy.ctr_zero)
    cr = (ps / clicks) if clicks > 0 else float(policy.cr_zero)
    arpu = (revenue / impressions) if impressions > 0 else float(policy.arpu_zero)

    top_offer_id = None
    top_offer_rev = float(policy.zero_amount)
    if offer_revenue:
        top_offer_id, top_offer_rev = max(offer_revenue.items(), key=lambda kv: kv[1])

    return {
        "impressions": impressions,
        "clicks": clicks,
        "purchases_success": ps,
        "purchases_failed": pf,
        "revenue": revenue,
        "ctr": ctr,
        "cr": cr,
        "arpu": arpu,
        "top_offer_id": top_offer_id,
        "top_offer_revenue": top_offer_rev,
    }

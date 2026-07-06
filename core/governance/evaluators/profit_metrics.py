from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, Protocol

from config.profit_metrics_policy import DEFAULT_PROFIT_METRICS_POLICY, ProfitMetricsPolicy
from core.events.event_types import PURCHASE_SUCCESS
from core.growth.spend_ledger_event_store import EventStoreSpendLedger


class EventStore(Protocol):
    def latest_events(self, *, tenant_id: str, event_types=None, event_type=None, limit: int = 20000) -> list[dict]: ...


def _to_utc_dt(ts: Any) -> datetime | None:
    if ts is None:
        return None
    if isinstance(ts, datetime):
        return ts.astimezone(UTC)
    try:
        if isinstance(ts, int | float):
            v = float(ts)
            if v > 2_000_000_000_000:
                return datetime.fromtimestamp(v / DEFAULT_PROFIT_METRICS_POLICY.minor_units_multiplier, tz=UTC)
            return datetime.fromtimestamp(v, tz=UTC)
        s = str(ts).replace("Z", "+00:00")
        d = datetime.fromisoformat(s)
        return d.astimezone(UTC)
    except Exception:
        return None


def _major_to_minor(amount_major: Any, *, multiplier: float | None = None) -> int:
    try:
        effective_multiplier = DEFAULT_PROFIT_METRICS_POLICY.minor_units_multiplier if multiplier is None else float(multiplier)
        return int(round(float(amount_major or 0) * effective_multiplier))
    except Exception:
        return 0


@dataclass(frozen=True)
class ProfitSnapshot:
    tenant_id: str
    lookback_days: int
    revenue_minor: int
    ads_spend_minor: int
    profit_minor: int


class ProfitMetricsService:
    """Single source of truth for profit = revenue - ads spend from event stream."""

    def __init__(self, *, event_store: EventStore, policy: ProfitMetricsPolicy | None = None) -> None:
        self._store = event_store
        self._ledger = EventStoreSpendLedger(event_store=event_store)
        self._policy = policy or DEFAULT_PROFIT_METRICS_POLICY

    def profit_lookback(self, *, tenant_id: str, lookback_days: int) -> ProfitSnapshot:
        tenant_id = str(tenant_id)
        lookback_days = int(lookback_days)
        now = datetime.now(UTC)
        since = now - timedelta(days=lookback_days)

        revenue_minor = 0
        try:
            events = self._store.latest_events(
                tenant_id=tenant_id,
                event_types=(PURCHASE_SUCCESS,),
                limit=int(self._policy.revenue_events_limit),
            )
        except Exception:
            events = []

        for e in events:
            if not isinstance(e, dict):
                continue
            ts = _to_utc_dt(
                e.get("ts") or e.get("created_at") or e.get("time") or e.get("timestamp") or e.get("timestamp_ms")
            )
            if ts is None or ts < since:
                continue
            payload = e.get("payload") or {}
            revenue_minor += _major_to_minor(
                payload.get("amount") or payload.get("amount_major"),
                multiplier=float(self._policy.minor_units_multiplier),
            )

        ads_spend_minor = self._sum_ads_spend_imported_minor(tenant_id=tenant_id, since=since)
        profit_minor = int(revenue_minor) - int(ads_spend_minor)
        return ProfitSnapshot(
            tenant_id=tenant_id,
            lookback_days=lookback_days,
            revenue_minor=int(revenue_minor),
            ads_spend_minor=int(ads_spend_minor),
            profit_minor=int(profit_minor),
        )

    def today_spend_minor(self, *, tenant_id: str) -> int:
        return int(self._ledger.today_spend_minor(tenant_id=str(tenant_id)))

    def _sum_ads_spend_imported_minor(self, *, tenant_id: str, since: datetime) -> int:
        try:
            events = self._store.latest_events(
                tenant_id=str(tenant_id),
                event_types=("ads_metrics_imported",),
                limit=int(self._policy.ads_metrics_limit),
            )
        except Exception:
            return 0

        total_major = 0
        for e in events:
            if not isinstance(e, dict):
                continue
            ts = _to_utc_dt(e.get("timestamp_ms") or e.get("ts") or e.get("created_at") or e.get("timestamp"))
            if ts is None or ts < since:
                continue
            payload = e.get("payload") or {}
            metrics = payload.get("metrics") or {}
            try:
                total_major += float(metrics.get("spend") or 0)
            except Exception:
                continue
        return _major_to_minor(total_major, multiplier=float(self._policy.minor_units_multiplier))

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, Protocol

from config.profit_metrics_policy import DEFAULT_PROFIT_METRICS_POLICY, ProfitMetricsPolicy
from core.events.event_types import (
    ADS_ATTRIBUTION_MATURITY_SNAPSHOT,
    PURCHASE_SUCCESS,
)
from core.growth.spend_ledger_event_store import EventStoreSpendLedger

_DAY_MS = 24 * 60 * 60 * 1000
_MILLISECONDS_THRESHOLD = 100_000_000_000


class EventStore(Protocol):
    def latest_events(self, *, tenant_id: str, event_types=None, event_type=None, limit: int = 20000) -> list[dict]: ...


def _to_utc_dt(ts: Any) -> datetime | None:
    if ts is None:
        return None
    if isinstance(ts, datetime):
        return (
            ts.replace(tzinfo=UTC)
            if ts.tzinfo is None
            else ts.astimezone(UTC)
        )
    try:
        if isinstance(ts, int | float):
            v = float(ts)
            if abs(v) >= _MILLISECONDS_THRESHOLD:
                return datetime.fromtimestamp(v / 1000.0, tz=UTC)
            return datetime.fromtimestamp(v, tz=UTC)
        raw = str(ts).strip()
        try:
            return _to_utc_dt(float(raw))
        except (TypeError, ValueError):
            pass
        s = raw.replace("Z", "+00:00")
        d = datetime.fromisoformat(s)
        return (
            d.replace(tzinfo=UTC)
            if d.tzinfo is None
            else d.astimezone(UTC)
        )
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
        return self._profit_between(
            tenant_id=tenant_id,
            start=since,
            end=now,
            lookback_days=lookback_days,
        )

    def profit_between_ms(
        self,
        *,
        tenant_id: str,
        start_ms: int,
        end_ms: int,
    ) -> ProfitSnapshot:
        start = _to_utc_dt(int(start_ms))
        end = _to_utc_dt(int(end_ms))
        if start is None or end is None or end <= start:
            raise ValueError("INVALID_PROFIT_WINDOW")
        duration_ms = int(end_ms) - int(start_ms)
        lookback_days = max(1, (duration_ms + _DAY_MS - 1) // _DAY_MS)
        return self._profit_between(
            tenant_id=str(tenant_id),
            start=start,
            end=end,
            lookback_days=int(lookback_days),
        )

    def decision_executed_at_ms(
        self,
        *,
        tenant_id: str,
        decision_id: str,
    ) -> int | None:
        tenant = str(tenant_id).strip()
        decision = str(decision_id).strip()
        if not tenant or not decision:
            return None
        try:
            events = self._store.latest_events(
                tenant_id=tenant,
                event_types=(ADS_ATTRIBUTION_MATURITY_SNAPSHOT,),
                limit=int(self._policy.ads_metrics_limit),
            )
        except Exception:
            return None

        anchors: list[int] = []
        for event in events:
            if not isinstance(event, dict):
                continue
            payload = event.get("payload") or {}
            if not isinstance(payload, dict):
                payload = {}
            event_decision = str(
                event.get("decision_id")
                or payload.get("decision_id")
                or ""
            ).strip()
            if event_decision != decision:
                continue
            anchor = _to_utc_dt(
                payload.get("created_ms")
                or event.get("timestamp_ms")
                or event.get("ts")
                or event.get("created_at")
            )
            if anchor is not None:
                anchors.append(int(anchor.timestamp() * 1000))
        return min(anchors) if anchors else None

    def _profit_between(
        self,
        *,
        tenant_id: str,
        start: datetime,
        end: datetime,
        lookback_days: int,
    ) -> ProfitSnapshot:
        tenant_id = str(tenant_id)

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
                e.get("timestamp_ms")
                or e.get("ts")
                or e.get("created_at")
                or e.get("time")
                or e.get("timestamp")
            )
            if ts is None or ts < start or ts >= end:
                continue
            payload = e.get("payload") or {}
            if not isinstance(payload, dict):
                continue
            revenue_minor += _major_to_minor(
                payload.get("amount") or payload.get("amount_major"),
                multiplier=float(self._policy.minor_units_multiplier),
            )

        ads_spend_minor = self._sum_ads_spend_imported_minor(
            tenant_id=tenant_id,
            since=start,
            until=end,
        )
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

    def _sum_ads_spend_imported_minor(
        self,
        *,
        tenant_id: str,
        since: datetime,
        until: datetime,
    ) -> int:
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
            if ts is None or ts < since or ts >= until:
                continue
            payload = e.get("payload") or {}
            if not isinstance(payload, dict):
                continue
            metrics = payload.get("metrics") or {}
            if not isinstance(metrics, dict):
                continue
            try:
                total_major += float(metrics.get("spend") or 0)
            except Exception:
                continue
        return _major_to_minor(total_major, multiplier=float(self._policy.minor_units_multiplier))

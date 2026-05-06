from __future__ import annotations

"""Canonical supply-state owner surface."""

from dataclasses import asdict
from contracts.supply import BusinessLiveState
from registry.base_registry import BaseRegistry
from registry.business_state_feed_registry import BusinessStateFeedRegistry
from shared.numbers import coerce_float
from supply_state.feeds.crm_state_feed import CrmStateFeed
from supply_state.feeds.calendar_state_feed import CalendarStateFeed
from supply_state.feeds.revenue_state_feed import RevenueStateFeed
from supply_state.feeds.lead_pipeline_state_feed import LeadPipelineStateFeed
from supply_state.feeds.review_state_feed import ReviewStateFeed
from supply_state.feeds.response_time_feed import ResponseTimeFeed
from supply_state.feeds.refund_state_feed import RefundStateFeed
from supply_state.feeds.ad_performance_state_feed import AdPerformanceStateFeed

class BusinessCapacityEstimator:
    def estimate(self, feed_snapshot: dict[str, object]) -> float:
        slots = int(feed_snapshot.get("available_slots") or 0)
        queue_load = float(feed_snapshot.get("queue_load") or 0.0)
        return max(0.0, min(1.0, (slots / max(1, slots + 1)) * (1.0 - queue_load)))

class BusinessClosureRateEstimator:
    def estimate(self, feed_snapshot: dict[str, object]) -> float:
        return max(0.0, min(1.0, float(feed_snapshot.get("conversion_score") or 0.4)))

class BusinessConversionEstimator:
    def estimate(self, feed_snapshot: dict[str, object]) -> float:
        return max(0.0, min(1.0, float(feed_snapshot.get("conversion_score") or 0.4)))

class BusinessGeoFitEstimator:
    def estimate(self, feed_snapshot: dict[str, object]) -> float:
        return max(0.0, min(1.0, 1.0 - float(feed_snapshot.get("queue_load") or 0.0) * 0.2))

class BusinessLtvEstimator:
    def estimate(self, feed_snapshot: dict[str, object]) -> float:
        return max(0.0, min(1.0, float(feed_snapshot.get("ltv_score") or 0.5)))

class BusinessMarginEstimator:
    def estimate(self, feed_snapshot: dict[str, object]) -> float:
        return max(0.0, min(1.0, float(feed_snapshot.get("margin_score") or 0.5)))

class BusinessQueueLoadEstimator:
    def estimate(self, feed_snapshot: dict[str, object]) -> float:
        return max(0.0, min(1.0, float(feed_snapshot.get("queue_load") or 0.0)))

class BusinessRefundRiskEstimator:
    def estimate(self, feed_snapshot: dict[str, object]) -> float:
        return max(0.0, min(1.0, float(feed_snapshot.get("refund_risk") or 0.1)))

class BusinessReputationEstimator:
    def estimate(self, feed_snapshot: dict[str, object]) -> float:
        return max(0.0, min(1.0, float(feed_snapshot.get("reputation_score") or 0.5)))

class BusinessResponseSpeedEstimator:
    def estimate(self, feed_snapshot: dict[str, object]) -> float:
        return max(0.0, min(1.0, float(feed_snapshot.get("response_speed_score") or 0.5)))

class BusinessServiceFitEstimator:
    def estimate(self, feed_snapshot: dict[str, object]) -> float:
        return max(0.0, min(1.0, float(feed_snapshot.get("service_fit") or 0.5)))

class BusinessTimeFitEstimator:
    def estimate(self, feed_snapshot: dict[str, object]) -> float:
        return max(0.0, min(1.0, 0.7 if feed_snapshot.get("open_now", True) else 0.1))

class BusinessStateRegistry(BaseRegistry):
    def __init__(self) -> None:
        super().__init__(kind='business_state')

    def put(self, business_id: str, payload: dict[str, object]) -> None:
        self.register(str(business_id), dict(payload))

    def has(self, business_id: str) -> bool:
        return str(business_id) in self.snapshot()

    def get(self, business_id: str) -> dict[str, object]:
        try:
            row = super().get(str(business_id))
        except KeyError:
            return {}
        return dict(row if isinstance(row, dict) else {})

    def require(self, business_id: str) -> dict[str, object]:
        row = self.get(business_id)
        if not row:
            raise KeyError(str(business_id))
        return row

class FeedSnapshotMerger:
    def merge(self, parts: tuple[dict[str, object], ...]) -> dict[str, object]:
        merged: dict[str, object] = {}
        sources: list[str] = []
        for part in parts:
            fragment = dict(part)
            source = str(fragment.pop('_source', '') or 'unknown')
            sources.append(source)
            for key, value in fragment.items():
                if value is None:
                    continue
                merged[key] = value
        merged['_sources'] = tuple(sources)
        return merged

def from_snapshot(row: dict[str, object] | None, business_id: str) -> BusinessLiveState | None:
    if not isinstance(row, dict):
        return None
    features = row.get('features') or {}
    if not isinstance(features, dict):
        features = {}
    return BusinessLiveState(
        business_id=str(row.get('business_id') or business_id),
        open_now=bool(row.get('open_now', False)),
        capacity_score=coerce_float(row.get('capacity_score'), 0.0),
        queue_load=coerce_float(row.get('queue_load'), 0.0),
        response_speed_score=coerce_float(row.get('response_speed_score'), 0.0),
        conversion_score=coerce_float(row.get('conversion_score'), 0.0),
        quality_score=coerce_float(row.get('quality_score'), 0.0),
        risk_score=coerce_float(row.get('risk_score'), 0.0),
        reputation_score=coerce_float(row.get('reputation_score'), 0.0),
        margin_score=coerce_float(row.get('margin_score'), 0.0),
        features={str(key): coerce_float(value, 0.0) for key, value in features.items()},
    )

def to_snapshot(state: BusinessLiveState) -> dict[str, object]:
    features = getattr(state, 'features', {}) or {}
    if not isinstance(features, dict):
        features = {}
    return {
        'business_id': state.business_id,
        'open_now': bool(state.open_now),
        'capacity_score': coerce_float(state.capacity_score),
        'queue_load': coerce_float(state.queue_load),
        'response_speed_score': coerce_float(state.response_speed_score),
        'conversion_score': coerce_float(state.conversion_score),
        'quality_score': coerce_float(state.quality_score),
        'risk_score': coerce_float(state.risk_score),
        'reputation_score': coerce_float(state.reputation_score),
        'margin_score': coerce_float(state.margin_score),
        'features': {str(key): coerce_float(value, 0.0) for key, value in features.items()},
    }

class BusinessLiveStateBuilder:
    def __init__(self) -> None:
        self._registry = BusinessStateRegistry()
        self._feed_registry = BusinessStateFeedRegistry()
        self._merger = FeedSnapshotMerger()
        self._register_default_feeds()
        self._capacity = BusinessCapacityEstimator()
        self._queue = BusinessQueueLoadEstimator()
        self._response = BusinessResponseSpeedEstimator()
        self._conversion = BusinessConversionEstimator()
        self._risk = BusinessRefundRiskEstimator()
        self._reputation = BusinessReputationEstimator()
        self._margin = BusinessMarginEstimator()
        self._service = BusinessServiceFitEstimator()
        self._geo = BusinessGeoFitEstimator()
        self._time = BusinessTimeFitEstimator()

    def _register_default_feeds(self) -> None:
        for name, feed in (
            ('crm', CrmStateFeed()),
            ('calendar', CalendarStateFeed()),
            ('revenue', RevenueStateFeed()),
            ('lead_pipeline', LeadPipelineStateFeed()),
            ('reviews', ReviewStateFeed()),
            ('response_time', ResponseTimeFeed()),
            ('refunds', RefundStateFeed()),
            ('ad_performance', AdPerformanceStateFeed()),
        ):
            self._feed_registry.register(name, feed)

    def _fetch_parts(self, business_id: str) -> tuple[dict[str, object], ...]:
        parts: list[dict[str, object]] = []
        for _, feed in self._feed_registry.items():
            fetch = getattr(feed, 'fetch', None)
            if callable(fetch):
                parts.append(dict(fetch(str(business_id))))
        return tuple(parts)

    def build(self, business_id: str) -> BusinessLiveState:
        parts = self._fetch_parts(str(business_id))
        snapshot = self._merger.merge(parts)
        self._registry.put(str(business_id), snapshot)
        reputation_score = self._reputation.estimate(snapshot)
        service_score = self._service.estimate(snapshot)
        return BusinessLiveState(
            business_id=str(business_id),
            open_now=bool(snapshot.get('open_now', True)),
            capacity_score=self._capacity.estimate(snapshot),
            queue_load=self._queue.estimate(snapshot),
            response_speed_score=self._response.estimate(snapshot),
            conversion_score=self._conversion.estimate(snapshot),
            quality_score=max(0.0, min(1.0, (reputation_score + service_score) / 2.0)),
            risk_score=self._risk.estimate(snapshot),
            reputation_score=reputation_score,
            margin_score=self._margin.estimate(snapshot),
            features={
                'geo_fit': self._geo.estimate(snapshot),
                'time_fit': self._time.estimate(snapshot),
                'feed_sources': tuple(snapshot.get('_sources') or ()),
            },
        )

_MODULE_EXPORTS = {name: {name[0].upper()+name[1:]: f'supply_state:{name[0].upper()+name[1:]}' } for name in []}
_MODULE_EXPORTS = {
    'business_capacity_estimator': {'BusinessCapacityEstimator': 'supply_state:BusinessCapacityEstimator'},
    'business_closure_rate_estimator': {'BusinessClosureRateEstimator': 'supply_state:BusinessClosureRateEstimator'},
    'business_conversion_estimator': {'BusinessConversionEstimator': 'supply_state:BusinessConversionEstimator'},
    'business_geo_fit_estimator': {'BusinessGeoFitEstimator': 'supply_state:BusinessGeoFitEstimator'},
    'business_live_state_builder': {'BusinessLiveStateBuilder': 'supply_state:BusinessLiveStateBuilder'},
    'business_ltv_estimator': {'BusinessLtvEstimator': 'supply_state:BusinessLtvEstimator'},
    'business_margin_estimator': {'BusinessMarginEstimator': 'supply_state:BusinessMarginEstimator'},
    'business_queue_load_estimator': {'BusinessQueueLoadEstimator': 'supply_state:BusinessQueueLoadEstimator'},
    'business_refund_risk_estimator': {'BusinessRefundRiskEstimator': 'supply_state:BusinessRefundRiskEstimator'},
    'business_reputation_estimator': {'BusinessReputationEstimator': 'supply_state:BusinessReputationEstimator'},
    'business_response_speed_estimator': {'BusinessResponseSpeedEstimator': 'supply_state:BusinessResponseSpeedEstimator'},
    'business_service_fit_estimator': {'BusinessServiceFitEstimator': 'supply_state:BusinessServiceFitEstimator'},
    'business_state_registry': {'BusinessStateRegistry': 'supply_state:BusinessStateRegistry'},
    'business_time_fit_estimator': {'BusinessTimeFitEstimator': 'supply_state:BusinessTimeFitEstimator'},
    'feed_snapshot_merger': {'FeedSnapshotMerger': 'supply_state:FeedSnapshotMerger'},
    'live_state_snapshot': {'from_snapshot': 'supply_state:from_snapshot', 'to_snapshot': 'supply_state:to_snapshot'},
}

__all__ = list({export for module in _MODULE_EXPORTS.values() for export in module}) + ['BusinessLiveState']

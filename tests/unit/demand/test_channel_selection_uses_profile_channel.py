from __future__ import annotations

from contracts.matching.match_bundle import MatchBundle
from contracts.matching.match_candidate import MatchCandidate
from contracts.supply import BusinessSupplyProfile
from routing.demand_router import DemandRouter


class Directory:
    def list_profiles(self):
        return (
            BusinessSupplyProfile(
                business_id='biz-1',
                name='A',
                service_categories=('general',),
                service_area_codes=('amsterdam',),
                price_band='mid',
                notification_channels=('telegram', 'email'),
                tags=(),
                active=True,
            ),
        )


class StateBuilder:
    class S:
        business_id = 'biz-1'
        capacity_score = 0.8
        response_speed_score = 0.8
        risk_score = 0.1
        reputation_score = 0.8
        margin_score = 0.5
        queue_load = 0.2
        open_now = True
        conversion_score = 0.5
        quality_score = 0.8
        features = {}

    def build(self, business_id: str):
        return self.S()


class Request:
    request_id = 'r1'
    channel = 'website'


class Intent:
    is_high_value = False
    location_hint = ''
    quality_band = 'mid'


def test_router_trace_prefers_profile_delivery_channel() -> None:
    router = DemandRouter(business_directory=Directory(), business_live_state_builder=StateBuilder())
    bundle = MatchBundle('r1', (MatchCandidate('biz-1', 0.7, {'x': 0.7}, ('ok',), False),), {'live_state_snapshots': {'biz-1': {'business_id': 'biz-1', 'open_now': True, 'capacity_score': 0.8, 'queue_load': 0.2, 'response_speed_score': 0.8, 'conversion_score': 0.5, 'quality_score': 0.8, 'risk_score': 0.1, 'reputation_score': 0.8, 'margin_score': 0.5, 'features': {}}}})
    prepared = router.prepare(request=Request(), intent=Intent(), match_bundle=bundle)
    assert prepared['trace']['delivery_channel'] == 'telegram'

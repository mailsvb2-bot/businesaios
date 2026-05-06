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
                notification_channels=('telegram',),
                tags=(),
                active=True,
            ),
        )


class StateBuilder:
    def build(self, business_id: str):
        raise AssertionError('router must reuse match snapshot')


class Request:
    request_id = 'r1'
    channel = 'website'


class Intent:
    is_high_value = False
    location_hint = 'amsterdam'
    quality_band = 'mid'


def test_router_coerces_malformed_snapshot_values() -> None:
    router = DemandRouter(business_directory=Directory(), business_live_state_builder=StateBuilder())
    bundle = MatchBundle(
        'r1',
        (MatchCandidate('biz-1', 0.7, {'x': 0.7}, ('ok',), False),),
        {
            'live_state_snapshots': {
                'biz-1': {
                    'business_id': 'biz-1',
                    'open_now': True,
                    'capacity_score': 'bad',
                    'queue_load': None,
                    'response_speed_score': float('inf'),
                    'conversion_score': 0.5,
                    'quality_score': 0.6,
                    'risk_score': '0.2',
                    'reputation_score': {},
                    'margin_score': [],
                    'features': {'geo_fit': 'bad', 'time_fit': object()},
                }
            }
        },
    )
    prepared = router.prepare(request=Request(), intent=Intent(), match_bundle=bundle)
    assert prepared['request_id'] == 'r1'
    assert prepared['trace']['candidate_count'] in {0, 1}

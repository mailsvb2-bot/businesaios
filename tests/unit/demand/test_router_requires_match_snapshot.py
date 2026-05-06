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
    def build(self, business_id: str):
        raise AssertionError('router must not build a second live state line')


class Request:
    request_id = 'r1'
    channel = 'website'


class Intent:
    is_high_value = False
    location_hint = ''
    quality_band = 'mid'


def test_router_skips_candidate_without_match_snapshot() -> None:
    router = DemandRouter(business_directory=Directory(), business_live_state_builder=StateBuilder())
    bundle = MatchBundle('r1', (MatchCandidate('biz-1', 0.7, {'x': 0.7}, ('ok',), False),), {})
    prepared = router.prepare(request=Request(), intent=Intent(), match_bundle=bundle)
    assert prepared['requires_manual_review'] is True
    assert prepared['trace']['skipped_reasons']['biz-1'] == 'missing_match_live_state_snapshot'

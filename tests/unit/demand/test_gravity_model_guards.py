from __future__ import annotations

from contracts.demand import ClientIntent
from contracts.supply import BusinessLiveState, BusinessSupplyProfile
from demand_gravity.demand_gravity_model import DemandGravityModel


def test_gravity_model_tolerates_non_numeric_feature_values() -> None:
    vector = DemandGravityModel().vector_for(
        intent=ClientIntent(service_type='general', location_hint='amsterdam', needs_trust=True),
        profile=BusinessSupplyProfile(business_id='biz-1', service_area_codes=('amsterdam',), active=True),
        live_state=BusinessLiveState(
            business_id='biz-1',
            open_now=True,
            quality_score=0.8,
            response_speed_score=0.6,
            margin_score=0.5,
            features={'geo_fit': 'bad', 'time_fit': float('inf')},
        ),
    )
    assert 0.0 <= vector.attraction <= 1.0

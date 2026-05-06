from contracts.supply import BusinessLiveState
from supply_state.live_state_snapshot import from_snapshot, to_snapshot


def test_live_state_snapshot_roundtrip():
    state = BusinessLiveState(
        business_id='biz-1',
        open_now=True,
        capacity_score=0.8,
        queue_load=0.2,
        response_speed_score=0.9,
        conversion_score=0.5,
        quality_score=0.7,
        risk_score=0.1,
        reputation_score=0.8,
        margin_score=0.6,
        features={'geo_fit': 1.0},
    )
    rebuilt = from_snapshot(to_snapshot(state), 'biz-1')
    assert rebuilt == state

from __future__ import annotations

from supply_state.business_live_state_builder import BusinessLiveStateBuilder

def test_business_live_state_builder():
    state = BusinessLiveStateBuilder().build("biz-1")
    assert 0.0 <= state.capacity_score <= 1.0
    assert state.business_id == "biz-1"

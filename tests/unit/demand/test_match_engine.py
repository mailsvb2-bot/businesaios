from __future__ import annotations

from demand_capture.demand_capture_service import DemandCaptureService
from intent.client_intent_builder import ClientIntentBuilder
from supply_directory.business_directory import BusinessDirectory
from supply_state.business_live_state_builder import BusinessLiveStateBuilder
from matching.match_engine import MatchEngine

def test_match_engine():
    request = DemandCaptureService().capture({"text":"premium service near me", "channel":"website", "customer_id":"c1"})
    intent = ClientIntentBuilder().build(request)
    directory = BusinessDirectory(); directory.seed_defaults()
    profiles = directory.list_profiles()
    builder = BusinessLiveStateBuilder()
    live_states = tuple(builder.build(p.business_id) for p in profiles)
    bundle = MatchEngine().build_bundle(request=request, intent=intent, profiles=profiles, live_states=live_states)
    assert bundle.candidates

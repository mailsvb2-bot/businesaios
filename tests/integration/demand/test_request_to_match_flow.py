from __future__ import annotations

from demand_capture.demand_capture_service import DemandCaptureService
from intent.client_intent_builder import ClientIntentBuilder
from matching.match_engine import MatchEngine
from supply_directory.business_directory import BusinessDirectory
from supply_state.business_live_state_builder import BusinessLiveStateBuilder


def test_request_to_match_flow():
    request = DemandCaptureService().capture({"text":"need service near me", "channel":"website", "customer_id":"c1"})
    intent = ClientIntentBuilder().build(request)
    directory = BusinessDirectory()
    directory.seed_defaults()
    profiles = directory.list_profiles()
    states = tuple(BusinessLiveStateBuilder().build(p.business_id) for p in profiles)
    bundle = MatchEngine().build_bundle(request=request, intent=intent, profiles=profiles, live_states=states)
    assert bundle.request_id == request.request_id

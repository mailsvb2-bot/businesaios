from __future__ import annotations

from pathlib import Path

from demand_capture.demand_capture_service import DemandCaptureService
from intent.client_intent_builder import ClientIntentBuilder
from matching.match_engine import MatchEngine
from routing.demand_router import DemandRouter
from supply_directory.business_directory import BusinessDirectory
from supply_state.business_live_state_builder import BusinessLiveStateBuilder


def test_demand_router():
    request = DemandCaptureService().capture({"text":"premium service", "channel":"website", "customer_id":"c1"})
    intent = ClientIntentBuilder().build(request)
    directory = BusinessDirectory()
    directory.seed_defaults()
    state_builder = BusinessLiveStateBuilder()
    profiles = directory.list_profiles()
    bundle = MatchEngine().build_bundle(request=request, intent=intent, profiles=profiles, live_states=tuple(state_builder.build(p.business_id) for p in profiles))
    prepared = DemandRouter(business_directory=directory, business_live_state_builder=state_builder).prepare(request=request, intent=intent, match_bundle=bundle)
    assert "trace" in prepared
    assert "ranked_candidates" in prepared or prepared.get("requires_manual_review")



def test_demand_router_surface_is_collapsed() -> None:
    routing_dir = Path(__file__).resolve().parents[3] / "routing"
    assert not (routing_dir / "router_candidate_builder.py").exists()
    assert not (routing_dir / "router_ranker.py").exists()
    assert not (routing_dir / "router_input_builder.py").exists()

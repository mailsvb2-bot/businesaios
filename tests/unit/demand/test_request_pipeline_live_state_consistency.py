import pytest

from demand_os.request_pipeline import DemandRequestPipeline


class Capture:
    def capture(self, raw_event):
        return type('Request', (), {'request_id': 'req-1', 'customer_id': 'c-1'})()


class IntentBuilder:
    def build(self, request):
        return object()


class Profile:
    def __init__(self, business_id):
        self.business_id = business_id


class Directory:
    def list_profiles(self):
        return (Profile('biz-1'),)


class StateBuilder:
    def build(self, business_id):
        return type('LiveState', (), {'business_id': 'other-biz'})()


class Gravity:
    def vector_for(self, **kwargs):
        return object()


class MatchEngine:
    def build_bundle(self, **kwargs):
        return object()


class Router:
    def prepare(self, **kwargs):
        return {'request_id': 'req-1', 'ranked_candidates': (), 'trace': {}, 'requires_manual_review': True}


class Bridge:
    def route(self, **kwargs):
        return object()


class Delivery:
    def dispatch(self, **kwargs):
        return None


class Snapshot:
    request_count = 0
    decision_count = 0
    delivery_count = 0
    last_request_id = ''
    last_business_id = ''


class Optimizer:
    def current_state(self):
        return object()


def test_request_pipeline_rejects_mismatched_live_state_business_id() -> None:
    pipeline = DemandRequestPipeline(
        capture=Capture(),
        intent_builder=IntentBuilder(),
        business_directory=Directory(),
        state_builder=StateBuilder(),
        gravity_model=Gravity(),
        match_engine=MatchEngine(),
        router=Router(),
        decision_bridge=Bridge(),
        delivery_dispatcher=Delivery(),
        snapshot=Snapshot(),
    )
    with pytest.raises(ValueError):
        pipeline.process(raw_event={}, optimizer=Optimizer())

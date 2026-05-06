import pytest

from demand_os.request_pipeline import DemandRequestPipeline


class Capture:
    def capture(self, raw_event):
        return type('Request', (), {'request_id': 'req-1', 'customer_id': 'c-1'})()


class IntentBuilder:
    def build(self, request):
        return object()


class BadDirectory:
    pass


class StateBuilder:
    def build(self, business_id):
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



def test_request_pipeline_requires_directory_list_profiles() -> None:
    pipeline = DemandRequestPipeline(
        capture=Capture(),
        intent_builder=IntentBuilder(),
        business_directory=BadDirectory(),
        state_builder=StateBuilder(),
        gravity_model=object(),
        match_engine=MatchEngine(),
        router=Router(),
        decision_bridge=Bridge(),
        delivery_dispatcher=Delivery(),
        snapshot=Snapshot(),
    )
    with pytest.raises(ValueError):
        pipeline.process(raw_event={}, optimizer=Optimizer())

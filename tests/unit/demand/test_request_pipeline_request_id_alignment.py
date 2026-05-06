from contracts.demand import ClientRequest
from contracts.matching.match_bundle import MatchBundle
from contracts.matching.routing_decision import RoutingDecision
from demand_os.demand_os_snapshot import DemandOsSnapshot
from demand_os.request_pipeline import DemandRequestPipeline


class _Capture:
    def capture(self, _raw):
        return ClientRequest(request_id='req-1', text='x', channel='web', customer_id='c1')


class _Intent:
    def build(self, _request):
        return object()


class _Profile:
    business_id = 'biz-1'


class _Directory:
    def list_profiles(self):
        return (_Profile(),)


class _State:
    business_id = 'biz-1'


class _StateBuilder:
    def build(self, _business_id):
        return _State()


class _Gravity:
    def vector_for(self, **_kwargs):
        return object()


class _Match:
    def build_bundle(self, **_kwargs):
        return MatchBundle(request_id='other', candidates=(), audit={})


class _Router:
    def prepare(self, **_kwargs):
        return {'request_id': 'req-1', 'ranked_candidates': (), 'trace': {'request_id': 'req-1'}, 'requires_manual_review': True}


class _Bridge:
    def route(self, **_kwargs):
        return RoutingDecision(request_id='req-1', selected_business_id=None, trace={'decision_path': 'core.ai.decision_core'}, requires_manual_review=True)


class _Delivery:
    def dispatch(self, **_kwargs):
        return None


def test_request_pipeline_rejects_stage_request_id_divergence() -> None:
    pipeline = DemandRequestPipeline(
        capture=_Capture(),
        intent_builder=_Intent(),
        business_directory=_Directory(),
        state_builder=_StateBuilder(),
        gravity_model=_Gravity(),
        match_engine=_Match(),
        router=_Router(),
        decision_bridge=_Bridge(),
        delivery_dispatcher=_Delivery(),
        snapshot=DemandOsSnapshot(),
    )
    try:
        pipeline.process(raw_event={}, optimizer=type('O', (), {'current_state': lambda self: object()})())
    except ValueError as exc:
        assert 'match bundle request_id must match captured request' in str(exc)
    else:
        raise AssertionError('expected stage alignment failure')

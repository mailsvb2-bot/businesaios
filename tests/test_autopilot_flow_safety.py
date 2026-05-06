import asyncio

from core.growth.autopilot_config import AutopilotRunConfig
from core.growth.autopilot_engine import AutopilotEngine
from core.growth.autopilot_flow import queue_recommendations


class _Mode:
    value = "autopilot"


class _Ent:
    mode = _Mode()


class _Ents:
    def get_ads_entitlements(self, tenant_id):
        return _Ent()


class _Ads:
    async def import_stats(self, **kwargs):
        return 1


class _Reco:
    def propose_and_cache(self, **kwargs):
        return ({"id": "r1"}, {"id": "r2"}, {"id": "r3"})


class _Trust:
    def allow_autopilot(self, **kwargs):
        return True


class _Breaker:
    def is_tripped(self, **kwargs):
        return False


class _Sink:
    def __init__(self):
        self.events = []

    def emit(self, **kwargs):
        self.events.append(kwargs)


class _Gateway:
    def __init__(self):
        self.calls = []

    def propose(self, **kwargs):
        self.calls.append(kwargs)
        return f"gw-{len(self.calls)}"


def test_queue_recommendations_materializes_iterables_once():
    sink = _Sink()
    gw = _Gateway()
    engine = AutopilotEngine(
        entitlements_provider=_Ents(),
        ads_service=_Ads(),
        ads_reco_service=_Reco(),
        ads_apply_service=None,
        trust_score=_Trust(),
        circuit_breaker=_Breaker(),
        sink=sink,
        cfg=AutopilotRunConfig(max_applies_per_run=2),
        proposal_gateway=gw,
    )
    stats = queue_recommendations(
        engine=engine,
        tenant_id="t1",
        platform="meta",
        account_id="acc",
        recs=({"id": "r1"}, {"id": "r2"}, {"id": "r3"}),
        decision_id="d1",
        correlation_id="c1",
        issuer_id="businesaios-core",
    )
    assert stats["proposed"] == 3
    assert stats["queued"] == 2
    assert len(gw.calls) == 2


def test_autopilot_engine_compiles_and_runs_with_tuple_recommendations():
    sink = _Sink()
    gw = _Gateway()
    engine = AutopilotEngine(
        entitlements_provider=_Ents(),
        ads_service=_Ads(),
        ads_reco_service=_Reco(),
        ads_apply_service=None,
        trust_score=_Trust(),
        circuit_breaker=_Breaker(),
        sink=sink,
        cfg=AutopilotRunConfig(max_applies_per_run=2),
        proposal_gateway=gw,
    )
    out = asyncio.run(engine.run(tenant_id="t1", platform="meta", account_id="acc", decision_id="d1", correlation_id="c1"))
    assert out.ok is True
    assert out.proposed == 3
    assert out.queued == 2
